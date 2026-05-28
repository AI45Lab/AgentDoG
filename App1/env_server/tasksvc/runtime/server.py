import argparse
import copy
import json
import os
import random
import socket
import threading
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler

from tasksvc.assembly.bundle_validator import validate_runtime_bundle
from tasksvc.assembly.catalog_loader import load_runtime_catalog_from_file, normalize_runtime_catalog_payload
from tasksvc.rules.evaluation_hints import build_success_eval_rule
from tasksvc.runtime.reward_health import compute_training_reward
from tasksvc.runtime.runtime_evaluators import StepChecklistEvaluator, check_success
from tasksvc.runtime.tool_runtime import (
    EpisodeToolExecutor,
    ToolContractError,
    ToolRuntimeError,
    ToolSandboxConfig,
    ToolTimeoutError,
    ToolValidationError,
)

try:  # pragma: no cover - import guard for environments without FastAPI installed
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    import uvicorn
except ImportError:  # pragma: no cover - handled in main()
    FastAPI = None
    Request = None
    JSONResponse = None
    uvicorn = None


TASK_CATALOG = {}
EPISODES = {}
EPISODE_LOCKS = {}
EPISODE_EXECUTORS = {}
TOOL_SANDBOX_CONFIG = ToolSandboxConfig()
STEP_CHECKLIST_EVALUATOR = StepChecklistEvaluator()
EPISODE_TTL_SECONDS = 1800
MAX_EPISODES = 200
EPISODE_MAX_STEPS = 6
SERVER_INSTANCE_ID = uuid.uuid4().hex
SERVER_STARTED_AT = time.time()
SAMPLING_MODE = "random"
PAIRING_GROUPS = []
SAMPLER_QUEUE = []
SAMPLER_LOCK = threading.Lock()
GROUP_VARIANT_POLICY = "one_each"
GROUP_SHUFFLE_SEED = None



def _now():
    return time.time()


def _close_episode(episode_id):
    executor = EPISODE_EXECUTORS.pop(episode_id, None)
    if executor is not None:
        executor.close()
    EPISODES.pop(episode_id, None)
    EPISODE_LOCKS.pop(episode_id, None)


def _replace_episode_executor(episode):
    episode_id = episode["episode_id"]
    previous = EPISODE_EXECUTORS.get(episode_id)
    replacement = _build_episode_executor(episode["bundle"])
    EPISODE_EXECUTORS[episode_id] = replacement
    if previous is not None:
        previous.close()
    return replacement


def _release_episode_executor(episode_id):
    executor = EPISODE_EXECUTORS.pop(episode_id, None)
    if executor is not None:
        executor.close()


def cleanup_expired_episodes():
    now = _now()
    removable = []
    for episode_id, episode in list(EPISODES.items()):
        if episode.get("expires_at", now + 1) <= now:
            removable.append(episode_id)

    if len(EPISODES) - len(removable) > MAX_EPISODES:
        survivors = sorted(
            ((episode_id, episode) for episode_id, episode in EPISODES.items() if episode_id not in removable),
            key=lambda item: item[1].get("updated_at", item[1].get("created_at", 0)),
        )
        overflow = len(survivors) - MAX_EPISODES
        removable.extend([episode_id for episode_id, _ in survivors[:overflow]])

    for episode_id in set(removable):
        _close_episode(episode_id)


def catalog_public_view():
    items = []
    for bundle in TASK_CATALOG.values():
        task_spec = bundle["task_spec"]
        items.append({
            "task_id": task_spec["task_id"],
            "domain": task_spec["domain"],
            "difficulty_tier": task_spec["difficulty_tier"],
            "selected_tools": list(task_spec["selected_tools"]),
            "available_scenarios": list(task_spec.get("available_scenarios") or ["clean"]),
            "bundle_version": bundle["bundle_version"],
        })
    return sorted(items, key=lambda item: item["task_id"])


def register_catalog_payload(payload):
    catalog = normalize_runtime_catalog_payload(payload)
    for task_id, bundle in catalog.items():
        validate_runtime_bundle(bundle)
        TASK_CATALOG[task_id] = bundle
    return catalog


def _build_episode_executor(bundle):
    dispatch_table = bundle["server_adapter_manifest"]["tool_dispatch_table"]
    tool_impl_sources = bundle["execution_bundle"]["tool_impl_sources"]
    tool_programs = {}
    for tool_name, dispatch in dispatch_table.items():
        source_key = dispatch["source_key"]
        tool_programs[tool_name] = {
            "source_code": tool_impl_sources[source_key],
            "entrypoint_name": dispatch["entrypoint"],
        }
    return EpisodeToolExecutor(
        tool_programs,
        sandbox_config=TOOL_SANDBOX_CONFIG,
        thread_name=f"episode-tool-{bundle['task_spec']['task_id']}",
    )


def _set_path_value(container, dotted_path, value):
    path = [segment for segment in str(dotted_path or "").split(".") if segment]
    if not path:
        return container
    current = container
    for segment in path[:-1]:
        if segment not in current or not isinstance(current[segment], dict):
            current[segment] = {}
        current = current[segment]
    current[path[-1]] = copy.deepcopy(value)
    return container


def _deep_merge_dicts(base, overlay):
    if not isinstance(base, dict):
        return copy.deepcopy(overlay)
    merged = copy.deepcopy(base)
    if not isinstance(overlay, dict):
        return merged
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _subset_match(expected, actual):
    if not isinstance(expected, dict):
        return False
    if not isinstance(actual, dict):
        return False
    for key, value in expected.items():
        if key not in actual or actual[key] != value:
            return False
    return True


def _scenario_payload(bundle, scenario_name=None, attack_materialization=None):
    requested = str(scenario_name or bundle["task_spec"].get("default_scenario") or "clean").strip() or "clean"
    execution_scenarios = bundle["execution_bundle"].get("scenarios") or {}
    has_explicit_scenarios = bool(execution_scenarios)
    base_initial_state = copy.deepcopy(bundle["execution_bundle"]["initial_state_template"])
    scenario = copy.deepcopy(execution_scenarios.get(requested) or {})
    if not scenario:
        scenario = {
            "scenario": requested,
            "user_query": bundle["task_spec"]["user_query"],
            "initial_state_template": copy.deepcopy(base_initial_state),
            "tool_result_overlays": [],
            "risk_enabled": bool((bundle["task_spec"].get("risk_spec") or {}).get("enabled"))
            if not has_explicit_scenarios
            else requested != "clean" and bool((bundle["task_spec"].get("risk_spec") or {}).get("enabled")),
        }
    elif requested == "clean":
        scenario["initial_state_template"] = copy.deepcopy(base_initial_state)
    elif isinstance(scenario.get("initial_state_template"), dict):
        scenario["initial_state_template"] = _deep_merge_dicts(base_initial_state, scenario["initial_state_template"])
    else:
        scenario["initial_state_template"] = copy.deepcopy(base_initial_state)
    if attack_materialization:
        if isinstance(attack_materialization.get("attacked_user_query"), str) and attack_materialization.get("attacked_user_query").strip():
            scenario["user_query"] = attack_materialization["attacked_user_query"].strip()
        if isinstance(attack_materialization.get("initial_state_template"), dict):
            scenario["initial_state_template"] = _deep_merge_dicts(
                scenario.get("initial_state_template") or {},
                attack_materialization["initial_state_template"],
            )
        overlays = list(scenario.get("tool_result_overlays") or [])
        overlays.extend(copy.deepcopy(attack_materialization.get("tool_result_overlays") or []))
        scenario["tool_result_overlays"] = overlays
    scenario.setdefault("scenario", requested)
    scenario.setdefault("user_query", bundle["task_spec"]["user_query"])
    scenario.setdefault("initial_state_template", copy.deepcopy(base_initial_state))
    scenario.setdefault("tool_result_overlays", [])
    scenario.setdefault(
        "risk_enabled",
        bool((bundle["task_spec"].get("risk_spec") or {}).get("enabled"))
        if not has_explicit_scenarios
        else requested != "clean" and bool((bundle["task_spec"].get("risk_spec") or {}).get("enabled")),
    )
    return scenario


def build_episode(bundle, scenario_name=None, attack_materialization=None):
    cleanup_expired_episodes()
    now = _now()
    episode_id = f"ep_{uuid.uuid4().hex[:12]}"
    scenario = _scenario_payload(bundle, scenario_name=scenario_name, attack_materialization=attack_materialization)
    initial_state = copy.deepcopy(scenario["initial_state_template"])
    risk_enabled = bool(scenario.get("risk_enabled"))
    risk_spec = copy.deepcopy(bundle["task_spec"].get("risk_spec", {}))
    risk_config = copy.deepcopy(bundle["task_spec"].get("risk_config", {}))
    if not risk_enabled:
        risk_spec["enabled"] = False
        risk_config["enabled"] = False
    episode = {
        "episode_id": episode_id,
        "task_id": bundle["task_spec"]["task_id"],
        "scenario": scenario["scenario"],
        "bundle": bundle,
        "user_query": scenario["user_query"],
        "allowed_tools": list(bundle["tool_registry_view"]["allowed_tool_names"]),
        "tool_specs": copy.deepcopy(bundle["tool_registry_view"]["tool_schemas"]),
        "initial_state": copy.deepcopy(initial_state),
        "state": copy.deepcopy(initial_state),
        "success_spec": copy.deepcopy(bundle["execution_bundle"]["success_spec"]),
        "success_rule": copy.deepcopy(
            bundle["evaluation_bundle"].get("success_eval_rule")
            or build_success_eval_rule(bundle["execution_bundle"]["success_spec"])
        ),
        "utility_evaluation_spec": copy.deepcopy(bundle["evaluation_bundle"].get("utility_evaluation_spec") or {}),
        "evaluation_contract": copy.deepcopy(bundle["task_spec"].get("evaluation_contract", {})),
        "risk_spec": risk_spec,
        "risk_config": risk_config,
        "risk_success_rule": copy.deepcopy(bundle["evaluation_bundle"].get("risk_success_eval_rule") or {"type": "never"}) if risk_enabled else {"type": "never"},
        "risk_evaluation_spec": copy.deepcopy(bundle["evaluation_bundle"].get("risk_evaluation_spec") or {}) if risk_enabled else {},
        "utility_checklist": copy.deepcopy(bundle["evaluation_bundle"]["utility_checklist"]),
        "checklist_eval_hints": copy.deepcopy(bundle["evaluation_bundle"]["checklist_eval_hints"]),
        "risk_checklist": copy.deepcopy(bundle["evaluation_bundle"].get("risk_checklist", [])) if risk_enabled else [],
        "risk_checklist_eval_hints": copy.deepcopy(bundle["evaluation_bundle"].get("risk_checklist_eval_hints", {})) if risk_enabled else {},
        "tool_result_overlays": copy.deepcopy(scenario.get("tool_result_overlays") or []),
        "attack_materialization": copy.deepcopy(attack_materialization or {}),
        "checklist_progress": {},
        "risk_checklist_progress": {},
        "history": [],
        "turn_index": 0,
        "max_steps": EPISODE_MAX_STEPS,
        "created_at": now,
        "updated_at": now,
        "expires_at": now + EPISODE_TTL_SECONDS,
        "finished_at": None,
        "finish_reason": None,
        "final_answer": None,
        "success": False,
        "risk_success": False,
    }
    EPISODES[episode_id] = episode
    EPISODE_LOCKS[episode_id] = threading.Lock()
    EPISODE_EXECUTORS[episode_id] = _build_episode_executor(bundle)
    return episode


def validate_arguments(spec, arguments):
    if not isinstance(arguments, dict):
        return False, "Arguments must be a JSON object."
    required = spec["function"]["parameters"].get("required", [])
    missing = [key for key in required if key not in arguments]
    if missing:
        return False, f"Missing required arguments: {missing}"
    return True, None


def get_spec_for_tool(episode, tool_name):
    for spec in episode["tool_specs"]:
        if spec["function"]["name"] == tool_name:
            return spec
    raise KeyError(f"Tool schema not found for {tool_name}")


def execute_tool(episode, tool_name, arguments):
    bundle = episode["bundle"]
    context = {
        "task_id": episode["task_id"],
        "scenario": episode.get("scenario", "clean"),
        "tool_name": tool_name,
        "task_metadata": bundle["task_spec"]["task_metadata"],
        "risk_config": copy.deepcopy(episode.get("risk_config") or bundle["task_spec"]["risk_config"]),
        "risk_spec": copy.deepcopy(episode.get("risk_spec") or bundle["task_spec"].get("risk_spec", {})),
        "planner_trace": bundle["task_spec"]["planner_trace"],
        "attack_materialization": copy.deepcopy(episode.get("attack_materialization") or {}),
    }
    executor = EPISODE_EXECUTORS[episode["episode_id"]]
    result = executor.execute(
        tool_name,
        arguments,
        copy.deepcopy(episode["state"]),
        context,
    )
    for overlay in episode.get("tool_result_overlays") or []:
        if not isinstance(overlay, dict):
            continue
        if str(overlay.get("tool_name") or "").strip() != str(tool_name):
            continue
        if not _subset_match(overlay.get("match_arguments") or {}, arguments):
            continue
        tool_result_patch = overlay.get("tool_result_patch")
        if isinstance(tool_result_patch, dict):
            patched = copy.deepcopy(result.get("tool_result") or {})
            patched.update(copy.deepcopy(tool_result_patch))
            result["tool_result"] = patched
        observation_suffix = str(overlay.get("observation_suffix") or "").strip()
        if observation_suffix:
            result["observation"] = f"{result.get('observation', '')}\n{observation_suffix}".strip()
        state_patch = overlay.get("state_patch")
        if isinstance(state_patch, dict):
            for state_path, state_value in state_patch.items():
                _set_path_value(result.setdefault("state", {}), state_path, state_value)
    for field in bundle["response_contract"]["required_fields"]:
        if field not in result:
            raise ToolContractError(f"Tool result missing required field: {field}")
    if not isinstance(result["tool_result"], dict):
        raise ToolContractError("Tool result field tool_result must be a dict.")
    if not isinstance(result["observation"], str):
        raise ToolContractError("Tool result field observation must be a string.")
    if not isinstance(result["state"], dict):
        raise ToolContractError("Tool result field state must be a dict.")
    return result


def _tool_failure_payload(observation, error_type, step_reward=-0.5):
    return {
        "ok": True,
        "invalid_call": False,
        "tool_result": {},
        "observation": observation,
        "reward_info": {
            "step_reward": step_reward,
            "success": False,
            "error_type": error_type,
        },
    }


def load_task_catalog(backend, domain=None, llm_config=None, catalog_file=None):
    if not catalog_file:
        raise RuntimeError("This release package serves prebuilt runtime catalogs only. Pass --catalog-file.")
    catalog = load_runtime_catalog_from_file(catalog_file)
    for bundle in catalog.values():
        validate_runtime_bundle(bundle)
    return catalog


def _load_pairing_groups(pairing_file):
    groups = []
    if not pairing_file:
        return groups
    with open(pairing_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            group = json.loads(line)
            clean = group.get("clean") or {}
            if not clean.get("task_id"):
                continue
            groups.append(group)
    return groups


def _expand_pairing_groups(groups, seed=None):
    rng = random.Random(seed)
    shuffled = list(groups)
    rng.shuffle(shuffled)
    queue = []
    for group in shuffled:
        family_key = group.get("family_key") or group.get("base_family_key")
        clean = group.get("clean") or {}
        clean_id = clean.get("task_id")
        if not clean_id or clean_id not in TASK_CATALOG:
            continue
        local_items = [{"task_id": clean_id, "scenario": "clean", "task_type": "clean", "family_key": family_key}]
        for attack in group.get("attacks") or []:
            task_id = (attack or {}).get("task_id")
            if task_id in TASK_CATALOG:
                local_items.append({"task_id": task_id, "scenario": "attacked", "task_type": "attack", "family_key": family_key})
        for query in group.get("queries") or []:
            task_id = (query or {}).get("task_id")
            if task_id in TASK_CATALOG:
                local_items.append({"task_id": task_id, "scenario": "clean", "task_type": "query_target", "family_key": family_key})
        queue.extend(local_items)
    return queue


def _rebuild_sampler(seed=None):
    global SAMPLER_QUEUE, GROUP_SHUFFLE_SEED
    if seed is not None:
        GROUP_SHUFFLE_SEED = int(seed)
    if SAMPLING_MODE == "grouped_triplet":
        SAMPLER_QUEUE = _expand_pairing_groups(PAIRING_GROUPS, GROUP_SHUFFLE_SEED)
    else:
        SAMPLER_QUEUE = []
    return SAMPLER_QUEUE


def _next_sample_item():
    if SAMPLING_MODE != "grouped_triplet":
        bundle = random.choice(list(TASK_CATALOG.values()))
        return {"task_id": bundle["task_spec"]["task_id"], "scenario": "clean", "task_type": "clean", "family_key": None}
    with SAMPLER_LOCK:
        if not SAMPLER_QUEUE:
            _rebuild_sampler()
        if not SAMPLER_QUEUE:
            raise RuntimeError("grouped sampler is empty")
        return SAMPLER_QUEUE.pop(0)


def _episode_public_view(episode):
    public_episode = {
        "episode_id": episode["episode_id"],
        "task_id": episode["task_id"],
        "scenario": episode.get("scenario", "clean"),
        "user_query": episode["user_query"],
        "allowed_tools": episode["allowed_tools"],
        "history": episode["history"],
        "turn_index": episode["turn_index"],
        "max_steps": episode["max_steps"],
        "finished": episode.get("finished_at") is not None,
        "finished_at": episode.get("finished_at"),
        "finish_reason": episode.get("finish_reason"),
        "final_answer": episode.get("final_answer"),
        "success": episode["success"],
        "initial_state": episode["initial_state"],
        "state": episode["state"],
        "success_rule": episode["success_rule"],
        "risk_success_rule": episode["risk_success_rule"],
        "checklist_progress": episode["checklist_progress"],
    }
    if episode.get("risk_spec", {}).get("enabled"):
        public_episode["risk"] = {
            "enabled": True,
            "goal": episode["risk_spec"],
            "success": episode.get("risk_success", False),
            "checklist_progress": episode.get("risk_checklist_progress", {}),
        }
    return public_episode


def _finalize_episode(episode, final_answer=None, finish_reason=None):
    episode["final_answer"] = final_answer
    episode["finish_reason"] = finish_reason
    episode["finished_at"] = _now()
    episode["updated_at"] = episode["finished_at"]
    episode["expires_at"] = episode["updated_at"] + EPISODE_TTL_SECONDS
    episode["success"] = check_success(episode)
    try:
        evaluation = STEP_CHECKLIST_EVALUATOR.finalize(episode)
    except Exception as exc:
        risk_spec = episode.get("risk_spec") or {}
        evaluation = {
            "success": bool(episode.get("success")),
            "evaluation_mode": "evaluation_error_fallback",
            "checklist_progress": copy.deepcopy(episode.get("checklist_progress") or {}),
            "checklist_scores": {
                "subgoal_progress": 0.0,
                "final_task_completion": 1.0 if episode.get("success") else 0.0,
            },
            "error_type": "evaluation_finalize_error",
            "error_message": str(exc),
        }
        if risk_spec.get("enabled"):
            evaluation["risk_info"] = {
                "enabled": True,
                "goal": copy.deepcopy(risk_spec),
                "success": bool(episode.get("risk_success", False)),
                "checklist_progress": copy.deepcopy(episode.get("risk_checklist_progress") or {}),
                "checklist_scores": {"subgoal_progress": 0.0},
            }
    evaluation["training_reward"] = compute_training_reward(
        episode,
        final_answer=final_answer,
        truncated=str(finish_reason or "").lower() in {"max_turns_exhausted", "truncated", "max_tokens"},
    )
    _release_episode_executor(episode["episode_id"])
    return evaluation


def _handle_get(path):
    if path == "/health":
        cleanup_expired_episodes()
        return HTTPStatus.OK, {
            "ok": True,
            "task_count": len(TASK_CATALOG),
            "episode_count": len(EPISODES),
            "server_pid": os.getpid(),
            "server_instance_id": SERVER_INSTANCE_ID,
            "started_at": SERVER_STARTED_AT,
        }
    if path == "/catalog/tasks":
        cleanup_expired_episodes()
        return HTTPStatus.OK, {
            "ok": True,
            "tasks": catalog_public_view(),
        }
    if path.startswith("/episodes/"):
        cleanup_expired_episodes()
        episode_id = path.split("/")[-1]
        episode = EPISODES.get(episode_id)
        if not episode:
            return HTTPStatus.NOT_FOUND, {"ok": False, "error": "episode_not_found"}
        return HTTPStatus.OK, {"ok": True, "episode": _episode_public_view(episode)}
    return HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"}


def _handle_post(path, data):
    if path == "/catalog/register":
        try:
            catalog = register_catalog_payload(data)
        except Exception as exc:
            return HTTPStatus.BAD_REQUEST, {
                "ok": False,
                "error": "invalid_catalog_payload",
                "message": str(exc),
            }
        task_ids = sorted(catalog.keys())
        return HTTPStatus.OK, {
            "ok": True,
            "registered_count": len(task_ids),
            "task_ids": task_ids,
        }

    if path == "/catalog/register-batch":
        try:
            catalog = register_catalog_payload(data)
        except Exception as exc:
            return HTTPStatus.BAD_REQUEST, {
                "ok": False,
                "error": "invalid_catalog_payload",
                "message": str(exc),
            }
        task_ids = sorted(catalog.keys())
        return HTTPStatus.OK, {
            "ok": True,
            "registered_count": len(task_ids),
            "task_ids": task_ids,
        }

    if path == "/tasks/sample":
        cleanup_expired_episodes()
        try:
            item = _next_sample_item()
        except Exception as exc:
            return HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": "sample_failed", "message": str(exc)}
        bundle = TASK_CATALOG[item["task_id"]]
        payload = {
            "ok": True,
            "task_id": bundle["task_spec"]["task_id"],
            "scenario": item.get("scenario") or "clean",
            "task_type": item.get("task_type") or "clean",
            "family_key": item.get("family_key"),
            "user_query": bundle["task_spec"]["user_query"],
            "available_scenarios": list(bundle["task_spec"].get("available_scenarios") or ["clean"]),
            "available_tools": bundle["tool_registry_view"]["tool_schemas"],
            "task_metadata": {
                "domain": bundle["task_spec"].get("domain"),
                "difficulty_tier": bundle["task_spec"].get("difficulty_tier"),
                "bundle_version": bundle.get("bundle_version"),
                "sampling_mode": SAMPLING_MODE,
            },
        }
        return HTTPStatus.OK, payload

    if path == "/admin/reinit-sampler":
        seed = data.get("seed", GROUP_SHUFFLE_SEED)
        with SAMPLER_LOCK:
            queue = _rebuild_sampler(seed)
        return HTTPStatus.OK, {
            "ok": True,
            "sampling_mode": SAMPLING_MODE,
            "shuffle_seed": GROUP_SHUFFLE_SEED,
            "group_count": len(PAIRING_GROUPS),
            "queued_count": len(queue),
            "variant_policy": GROUP_VARIANT_POLICY,
        }

    if path == "/episodes/start":
        task_id = data.get("task_id")
        if not task_id or task_id not in TASK_CATALOG:
            return HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid_task_id"}
        scenario = str(data.get("scenario") or "clean").strip() or "clean"
        attack_materialization = data.get("attack_materialization")
        if attack_materialization is not None and not isinstance(attack_materialization, dict):
            return HTTPStatus.BAD_REQUEST, {
                "ok": False,
                "error": "invalid_attack_materialization",
                "message": "attack_materialization must be an object when provided.",
            }
        try:
            episode = build_episode(
                TASK_CATALOG[task_id],
                scenario_name=scenario,
                attack_materialization=attack_materialization,
            )
        except Exception as exc:
            return HTTPStatus.INTERNAL_SERVER_ERROR, {
                "ok": False,
                "error": "episode_start_failed",
                "message": str(exc),
            }
        return HTTPStatus.OK, {
            "ok": True,
            "episode_id": episode["episode_id"],
            "scenario": episode.get("scenario", "clean"),
            "user_query": episode["user_query"],
            "available_tools": episode["tool_specs"],
            "task_metadata": {
                "task_id": episode["task_id"],
                "domain": episode["bundle"]["task_spec"]["domain"],
                "difficulty_tier": episode["bundle"]["task_spec"]["difficulty_tier"],
                "available_scenarios": list(episode["bundle"]["task_spec"].get("available_scenarios") or ["clean"]),
                "benchmark_metadata": copy.deepcopy(
                    ((episode["bundle"]["task_spec"].get("task_metadata") or {}).get("benchmark_metadata") or {})
                ),
            },
        }

    if path.endswith("/finish") and path.startswith("/episodes/"):
        parts = path.strip("/").split("/")
        if len(parts) != 3:
            return HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"}
        episode_id = parts[1]
        episode = EPISODES.get(episode_id)
        if not episode:
            return HTTPStatus.NOT_FOUND, {"ok": False, "error": "episode_not_found"}
        episode_lock = EPISODE_LOCKS.get(episode_id)
        if episode_lock is None:
            return HTTPStatus.NOT_FOUND, {"ok": False, "error": "episode_not_found"}
        final_answer = data.get("final_answer")
        if final_answer is not None and not isinstance(final_answer, str):
            return HTTPStatus.BAD_REQUEST, {
                "ok": False,
                "error": "invalid_final_answer",
                "message": "final_answer must be a string or null.",
            }
        finish_reason = data.get("finish_reason")
        if finish_reason is not None and not isinstance(finish_reason, str):
            return HTTPStatus.BAD_REQUEST, {
                "ok": False,
                "error": "invalid_finish_reason",
                "message": "finish_reason must be a string or null.",
            }
        with episode_lock:
            if episode.get("finished_at") is not None:
                return HTTPStatus.BAD_REQUEST, {
                    "ok": False,
                    "error": "episode_already_finished",
                }
            evaluation = _finalize_episode(episode, final_answer=final_answer, finish_reason=finish_reason)
            public_episode = _episode_public_view(episode)
            _close_episode(episode_id)
            return HTTPStatus.OK, {
                "ok": True,
                "episode": public_episode,
                "evaluation": evaluation,
            }

    if path.endswith("/tool-call") and path.startswith("/episodes/"):
        parts = path.strip("/").split("/")
        if len(parts) != 3:
            return HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"}
        episode_id = parts[1]
        episode = EPISODES.get(episode_id)
        if not episode:
            return HTTPStatus.NOT_FOUND, {"ok": False, "error": "episode_not_found"}
        tool_name = data.get("tool_name")
        arguments = data.get("arguments", {})
        episode_lock = EPISODE_LOCKS.get(episode_id)
        if episode_lock is None:
            return HTTPStatus.NOT_FOUND, {"ok": False, "error": "episode_not_found"}

        with episode_lock:
            if episode.get("finished_at") is not None:
                return HTTPStatus.BAD_REQUEST, {
                    "ok": False,
                    "error": "episode_finished",
                }
            if tool_name not in episode["allowed_tools"]:
                return HTTPStatus.BAD_REQUEST, {
                    "ok": True,
                    "invalid_call": True,
                    "tool_result": {},
                    "observation": f"Tool {tool_name} is not allowed for this task.",
                    "reward_info": {"step_reward": -0.2, "success": False, "error_type": "tool_not_allowed"},
                }

            spec = get_spec_for_tool(episode, tool_name)
            valid, error = validate_arguments(spec, arguments)
            if not valid:
                error_type = "invalid_arguments_type" if not isinstance(arguments, dict) else "invalid_arguments"
                return HTTPStatus.BAD_REQUEST, {
                    "ok": True,
                    "invalid_call": True,
                    "tool_result": {},
                    "observation": error,
                    "reward_info": {"step_reward": -0.2, "success": False, "error_type": error_type},
                }

            try:
                execution_result = execute_tool(episode, tool_name, arguments)
            except ToolTimeoutError as exc:
                # A timed-out tool can leave the episode worker thread blocked.
                # Replace the executor so later calls are not permanently poisoned.
                _replace_episode_executor(episode)
                return HTTPStatus.OK, _tool_failure_payload(
                    f"Tool execution timed out: {exc}",
                    "tool_execution_timeout",
                )
            except ToolValidationError as exc:
                return HTTPStatus.OK, _tool_failure_payload(
                    f"Tool source validation failed: {exc}",
                    "tool_source_invalid",
                )
            except ToolContractError as exc:
                return HTTPStatus.OK, _tool_failure_payload(
                    f"Tool contract failed: {exc}",
                    "tool_contract_error",
                )
            except ToolRuntimeError as exc:
                return HTTPStatus.OK, _tool_failure_payload(
                    f"Tool execution failed: {exc}",
                    "tool_runtime_error",
                )
            except Exception as exc:
                return HTTPStatus.OK, _tool_failure_payload(
                    f"Unhandled server tool error: {exc}",
                    "tool_execution_error",
                )

            episode["state"] = execution_result["state"]
            episode["turn_index"] += 1
            episode["updated_at"] = _now()
            episode["expires_at"] = episode["updated_at"] + EPISODE_TTL_SECONDS
            episode["history"].append({
                "tool_name": tool_name,
                "arguments": arguments,
                "tool_result": execution_result["tool_result"],
                "observation": execution_result["observation"],
            })
            reward_info = STEP_CHECKLIST_EVALUATOR.evaluate(episode, tool_name, True, execution_result)
            reward_info["training_reward"] = compute_training_reward(episode)

            return HTTPStatus.OK, {
                "ok": True,
                "invalid_call": False,
                "tool_result": execution_result["tool_result"],
                "observation": execution_result["observation"],
                "reward_info": reward_info,
            }

    return HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"}


def _handle_delete(path):
    if path.startswith("/catalog/tasks/"):
        task_id = path.split("/")[-1]
        removed = TASK_CATALOG.pop(task_id, None)
        return HTTPStatus.OK, {
            "ok": True,
            "removed": removed is not None,
            "task_id": task_id,
        }
    if path.startswith("/episodes/"):
        episode_id = path.split("/")[-1]
        existed = episode_id in EPISODES
        _close_episode(episode_id)
        return HTTPStatus.OK, {
            "ok": True,
            "removed": existed,
            "episode_id": episode_id,
        }
    return HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"}


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _safe_read_json(self):
        try:
            data = self._read_json()
        except json.JSONDecodeError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {
                "ok": False,
                "error": "invalid_json",
                "message": f"Malformed JSON request body: {exc.msg}",
            })
            return None
        if not isinstance(data, dict):
            self._send_json(HTTPStatus.BAD_REQUEST, {
                "ok": False,
                "error": "invalid_request",
                "message": "Top-level JSON body must be an object.",
            })
            return None
        return data

    def do_GET(self):
        status, payload = _handle_get(self.path)
        self._send_json(status, payload)

    def do_POST(self):
        data = self._safe_read_json()
        if data is None:
            return
        status, payload = _handle_post(self.path, data)
        self._send_json(status, payload)

    def do_DELETE(self):
        status, payload = _handle_delete(self.path)
        self._send_json(status, payload)


def create_app():
    if FastAPI is None or JSONResponse is None:  # pragma: no cover - import guard
        raise RuntimeError("FastAPI and uvicorn are required to run the server. Install fastapi and uvicorn first.")

    app = FastAPI()

    @app.get("/health")
    async def health():
        status, payload = _handle_get("/health")
        return JSONResponse(status_code=int(status), content=payload)

    @app.get("/catalog/tasks")
    async def catalog_tasks():
        status, payload = _handle_get("/catalog/tasks")
        return JSONResponse(status_code=int(status), content=payload)

    @app.get("/episodes/{episode_id}")
    async def get_episode(episode_id: str):
        status, payload = _handle_get(f"/episodes/{episode_id}")
        return JSONResponse(status_code=int(status), content=payload)

    @app.post("/catalog/register")
    async def register_catalog(request: Request):
        data = await _fastapi_read_json(request)
        if isinstance(data, JSONResponse):
            return data
        status, payload = _handle_post("/catalog/register", data)
        return JSONResponse(status_code=int(status), content=payload)

    @app.post("/catalog/register-batch")
    async def register_catalog_batch(request: Request):
        data = await _fastapi_read_json(request)
        if isinstance(data, JSONResponse):
            return data
        status, payload = _handle_post("/catalog/register-batch", data)
        return JSONResponse(status_code=int(status), content=payload)

    @app.post("/tasks/sample")
    async def sample_task(request: Request):
        data = await _fastapi_read_json(request)
        if isinstance(data, JSONResponse):
            return data
        status, payload = _handle_post("/tasks/sample", data)
        return JSONResponse(status_code=int(status), content=payload)

    @app.post("/admin/reinit-sampler")
    async def reinit_sampler(request: Request):
        data = await _fastapi_read_json(request)
        if isinstance(data, JSONResponse):
            return data
        status, payload = _handle_post("/admin/reinit-sampler", data)
        return JSONResponse(status_code=int(status), content=payload)

    @app.post("/episodes/start")
    async def start_episode(request: Request):
        data = await _fastapi_read_json(request)
        if isinstance(data, JSONResponse):
            return data
        status, payload = _handle_post("/episodes/start", data)
        return JSONResponse(status_code=int(status), content=payload)

    @app.post("/episodes/{episode_id}/tool-call")
    async def tool_call(episode_id: str, request: Request):
        data = await _fastapi_read_json(request)
        if isinstance(data, JSONResponse):
            return data
        status, payload = _handle_post(f"/episodes/{episode_id}/tool-call", data)
        return JSONResponse(status_code=int(status), content=payload)

    @app.post("/episodes/{episode_id}/finish")
    async def finish_episode(episode_id: str, request: Request):
        data = await _fastapi_read_json(request)
        if isinstance(data, JSONResponse):
            return data
        status, payload = _handle_post(f"/episodes/{episode_id}/finish", data)
        return JSONResponse(status_code=int(status), content=payload)

    @app.delete("/catalog/tasks/{task_id}")
    async def delete_task(task_id: str):
        status, payload = _handle_delete(f"/catalog/tasks/{task_id}")
        return JSONResponse(status_code=int(status), content=payload)

    @app.delete("/episodes/{episode_id}")
    async def delete_episode(episode_id: str):
        status, payload = _handle_delete(f"/episodes/{episode_id}")
        return JSONResponse(status_code=int(status), content=payload)

    return app


def _assert_listen_port_available(host, port):
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind((host, int(port)))
    except OSError as exc:
        raise RuntimeError(f"Server port {host}:{port} is unavailable: {exc}") from exc
    finally:
        probe.close()


async def _fastapi_read_json(request):
    try:
        data = await request.json()
    except json.JSONDecodeError as exc:
        return JSONResponse(
            status_code=int(HTTPStatus.BAD_REQUEST),
            content={
                "ok": False,
                "error": "invalid_json",
                "message": f"Malformed JSON request body: {exc.msg}",
            },
        )
    except Exception:
        data = {}
    if data is None:
        data = {}
    if not isinstance(data, dict):
        return JSONResponse(
            status_code=int(HTTPStatus.BAD_REQUEST),
            content={
                "ok": False,
                "error": "invalid_request",
                "message": "Top-level JSON body must be an object.",
            },
        )
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--backend", choices=["placeholder", "llm"], default="placeholder")
    parser.add_argument("--domain", default=None)
    parser.add_argument("--catalog-file", default=None)
    parser.add_argument("--llm-base-url", default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-api-key", default=None)
    parser.add_argument("--llm-timeout", type=int, default=None)
    parser.add_argument("--llm-temperature", type=float, default=None)
    parser.add_argument("--plan-max-tokens", type=int, default=None)
    parser.add_argument("--query-max-tokens", type=int, default=None)
    parser.add_argument("--checklist-max-tokens", type=int, default=None)
    parser.add_argument("--tool-code-max-tokens", type=int, default=None)
    parser.add_argument("--tool-exec-timeout", type=float, default=None)
    parser.add_argument("--episode-ttl-seconds", type=int, default=None)
    parser.add_argument("--max-episodes", type=int, default=None)
    parser.add_argument("--episode-max-steps", type=int, default=None)
    parser.add_argument("--sampling-mode", choices=["random", "grouped_triplet"], default="random")
    parser.add_argument("--pairing-file", default=None)
    parser.add_argument("--group-variant-policy", default="one_each")
    parser.add_argument("--group-shuffle-seed", type=int, default=None)
    args = parser.parse_args()

    global TASK_CATALOG, EPISODES, TOOL_SANDBOX_CONFIG, EPISODE_TTL_SECONDS, MAX_EPISODES, EPISODE_MAX_STEPS, SAMPLING_MODE, PAIRING_GROUPS, GROUP_VARIANT_POLICY, GROUP_SHUFFLE_SEED
    EPISODES = {}
    EPISODE_LOCKS.clear()
    for episode_id in list(EPISODE_EXECUTORS):
        _close_episode(episode_id)
    llm_config = None
    if args.backend == "llm":
        raise RuntimeError("LLM generation is intentionally not included in this runtime release. Use --backend placeholder with --catalog-file.")
    if args.episode_ttl_seconds is not None:
        EPISODE_TTL_SECONDS = args.episode_ttl_seconds
    if args.max_episodes is not None:
        MAX_EPISODES = args.max_episodes
    if args.episode_max_steps is not None:
        EPISODE_MAX_STEPS = args.episode_max_steps
    TASK_CATALOG = load_task_catalog(args.backend, domain=args.domain, llm_config=llm_config, catalog_file=args.catalog_file)
    SAMPLING_MODE = args.sampling_mode
    GROUP_VARIANT_POLICY = args.group_variant_policy
    GROUP_SHUFFLE_SEED = args.group_shuffle_seed
    PAIRING_GROUPS = _load_pairing_groups(args.pairing_file) if args.pairing_file else []
    _rebuild_sampler(GROUP_SHUFFLE_SEED)
    TOOL_SANDBOX_CONFIG = ToolSandboxConfig()
    if args.tool_exec_timeout is not None:
        TOOL_SANDBOX_CONFIG.execution_timeout_seconds = args.tool_exec_timeout

    app = create_app()
    print(f"Serving on http://{args.host}:{args.port} using backend={args.backend}")
    if uvicorn is None:  # pragma: no cover - import guard
        raise RuntimeError("uvicorn is required to run the server. Install uvicorn first.")
    _assert_listen_port_available(args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
