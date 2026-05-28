import copy
import re

from tasksvc.assembly.bundle_validator import validate_runtime_bundle
from tasksvc.assembly.bundle_validator import validate_task_draft
from tasksvc.common.contracts import EXECUTOR_SIGNATURE, RESPONSE_CONTRACT, default_risk_success_rule
from tasksvc.generation.generator import build_default_static_task_drafts, build_llm_static_task_drafts
from tasksvc.generation.task_safety_perturber import TaskSafetyPerturber
from tasksvc.rules.evaluation_hints import build_success_eval_rule


def _public_tool_name(tool_name, used_names=None):
    text = str(tool_name or "").strip()
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", text):
        return text
    base = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower()
    if not base:
        base = "tool"
    if base[0].isdigit():
        base = f"tool_{base}"
    used = used_names if used_names is not None else set()
    candidate = base
    index = 2
    while candidate in used:
        candidate = f"{base}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def _rewrite_rule_tool_names(value, alias_map):
    if isinstance(value, dict):
        rewritten = {}
        for key, item in value.items():
            if key == "tool_name" and isinstance(item, str) and item in alias_map:
                rewritten[key] = alias_map[item]
            else:
                rewritten[key] = _rewrite_rule_tool_names(item, alias_map)
        return rewritten
    if isinstance(value, list):
        return [_rewrite_rule_tool_names(item, alias_map) for item in value]
    return value


def assemble_runtime_bundle(task_draft):
    validate_task_draft(task_draft)
    planned_task = task_draft["planned_task"]
    agent_input_view = task_draft["agent_input_view"]
    state_draft = task_draft["state_draft"]
    utility_checklist_draft = task_draft["utility_checklist_draft"]
    risk_checklist_draft = task_draft["risk_checklist_draft"]
    risk_config = copy.deepcopy(agent_input_view["risk_placeholders"]["risk_config"])
    selected_tools = list(planned_task["selected_tools"])
    success_rule = copy.deepcopy(state_draft.get("success_rule") or build_success_eval_rule(state_draft["success_spec"]))
    risk_success_rule = copy.deepcopy(state_draft.get("risk_success_rule") or default_risk_success_rule())
    scenario_specs = copy.deepcopy(state_draft.get("scenarios") or {})
    used_public_names = set()
    alias_map = {tool_name: _public_tool_name(tool_name, used_public_names) for tool_name in selected_tools}
    public_selected_tools = [alias_map[tool_name] for tool_name in selected_tools]
    public_tool_schemas = copy.deepcopy(agent_input_view["tool_schemas"])
    for schema in public_tool_schemas:
        function = schema.get("function") or {}
        original_name = function.get("name")
        if original_name in alias_map:
            function["x-original-name"] = original_name
            function["name"] = alias_map[original_name]
    success_rule = _rewrite_rule_tool_names(success_rule, alias_map)
    risk_success_rule = _rewrite_rule_tool_names(risk_success_rule, alias_map)

    dispatch_table = {}
    for tool_name in selected_tools:
        dispatch_table[alias_map[tool_name]] = {
            "source_key": tool_name,
            "entrypoint": "execute",
            "original_tool_name": tool_name,
        }

    bundle = {
        "bundle_version": "v1",
        "task_spec": {
            "task_id": planned_task["task_id"],
            "domain": planned_task["domain"],
            "difficulty_tier": planned_task["difficulty_tier"],
            "user_query": agent_input_view["user_query"],
            "available_scenarios": sorted(scenario_specs.keys()) if scenario_specs else ["clean"],
            "default_scenario": "clean",
            "selected_tools": public_selected_tools,
            "evaluation_contract": copy.deepcopy(task_draft["task_plan_spec"].get("evaluation_contract", {})),
            "risk_config": risk_config,
            "risk_spec": copy.deepcopy(task_draft["task_plan_spec"].get("risk_spec", {})),
            "safety_perturbation": copy.deepcopy(task_draft.get("safety_perturbation_draft", {})),
            "task_metadata": copy.deepcopy(planned_task["task_metadata"]),
            "planner_trace": copy.deepcopy(planned_task["planner_trace"]),
        },
        "tool_registry_view": {
            "tool_schemas": public_tool_schemas,
            "allowed_tool_names": public_selected_tools,
            "tool_name_aliases": copy.deepcopy(alias_map),
        },
        "execution_bundle": {
            "tool_impl_sources": copy.deepcopy(task_draft["tool_code_drafts"]),
            "tool_entrypoints": copy.deepcopy(dispatch_table),
            "initial_state_template": copy.deepcopy(state_draft["initial_state_template"]),
            "scenarios": copy.deepcopy(scenario_specs),
            "success_spec": copy.deepcopy(state_draft["success_spec"]),
        },
        "evaluation_bundle": {
            "utility_evaluation_spec": _rewrite_rule_tool_names(
                copy.deepcopy(task_draft["evaluation_spec_draft"]),
                alias_map,
            ),
            "utility_checklist": _rewrite_rule_tool_names(copy.deepcopy(utility_checklist_draft["items"]), alias_map),
            "checklist_eval_hints": _rewrite_rule_tool_names(
                copy.deepcopy(utility_checklist_draft["checklist_eval_hints"]),
                alias_map,
            ),
            "success_eval_rule": success_rule,
            "risk_evaluation_spec": _rewrite_rule_tool_names(
                copy.deepcopy(task_draft["risk_evaluation_spec_draft"]),
                alias_map,
            ),
            "risk_checklist": _rewrite_rule_tool_names(copy.deepcopy(risk_checklist_draft["items"]), alias_map),
            "risk_checklist_eval_hints": _rewrite_rule_tool_names(
                copy.deepcopy(risk_checklist_draft["checklist_eval_hints"]),
                alias_map,
            ),
            "risk_success_eval_rule": risk_success_rule,
        },
        "executor_contract": {
            "signature": EXECUTOR_SIGNATURE
        },
        "response_contract": copy.deepcopy(RESPONSE_CONTRACT),
        "server_adapter_manifest": {
            "state_init_key": "execution_bundle.initial_state_template",
            "tool_dispatch_table": copy.deepcopy(dispatch_table),
            "tool_name_aliases": copy.deepcopy(alias_map),
            "success_eval_type": state_draft["success_spec"]["type"],
            "checklist_eval_type": state_draft["success_spec"]["type"],
        }
    }
    validate_runtime_bundle(bundle)
    return bundle


def assemble_runtime_catalog(task_drafts, perturbation_config=None, progress=None):
    perturber = TaskSafetyPerturber(config=perturbation_config)
    processed_drafts = perturber.apply_to_drafts(task_drafts)
    bundles = []
    phase = progress.phase("Assemble bundles", len(processed_drafts)) if progress else None
    for task_draft in processed_drafts:
        bundles.append(assemble_runtime_bundle(task_draft))
        if phase:
            phase.advance(detail=task_draft["planned_task"]["task_id"])
    if phase:
        phase.close()
    return {bundle["task_spec"]["task_id"]: bundle for bundle in bundles}


def build_default_runtime_catalog(target_domain=None, perturbation_config=None):
    return assemble_runtime_catalog(
        build_default_static_task_drafts(target_domain=target_domain),
        perturbation_config=perturbation_config,
    )


def build_llm_runtime_catalog(target_domain=None, config=None, perturbation_config=None):
    return assemble_runtime_catalog(
        build_llm_static_task_drafts(target_domain=target_domain, config=config),
        perturbation_config=perturbation_config,
    )
