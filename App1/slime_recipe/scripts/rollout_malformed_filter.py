"""Rollout sample filter for malformed qwen3_coder tool-call XML.

This module is intended to be used through slime's
``--rollout-sample-filter-path rollout_malformed_filter.filter_malformed_tool_calls``.
It marks only clearly malformed tool-call trajectories as ``remove_sample=True`` so
they do not contribute to the policy loss.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


EOS_MARKERS = ("<|im_end|>", "<|endoftext|>")
BATCH_UTILITY_FALLBACK = float(os.getenv("SLIME_JUDGE_BATCH_UTILITY_FALLBACK", "0.5"))
MONITOR_OUTPUT_DIR = os.getenv("SLIME_ROLLOUT_MONITOR_DIR", os.getenv("SLIME_ENV_SERVER_MONITOR_DIR", "")).strip()
MONITOR_SHORT_RESPONSE_TOKENS = int(os.getenv("SLIME_ROLLOUT_MONITOR_SHORT_RESPONSE_TOKENS", "100"))
MONITOR_SAMPLE_MAX_PER_BUCKET = int(os.getenv("SLIME_ROLLOUT_MONITOR_SAMPLE_MAX_PER_BUCKET", "8"))
MONITOR_KEEP_NORMAL_SAMPLES = int(os.getenv("SLIME_ROLLOUT_MONITOR_KEEP_NORMAL_SAMPLES", "2"))
MONITOR_ENABLE_SAMPLE_BUCKETS = os.getenv("SLIME_ROLLOUT_MONITOR_SAMPLE_BUCKETS", "1").lower() in (
    "1",
    "true",
    "yes",
)
MONITOR_INCLUDE_PROMPT = os.getenv("SLIME_ROLLOUT_MONITOR_INCLUDE_PROMPT", "1").lower() in ("1", "true", "yes")
MONITOR_INCLUDE_TOKENS = os.getenv("SLIME_ROLLOUT_MONITOR_INCLUDE_TOKENS", "0").lower() in ("1", "true", "yes")
COLLAPSE_DETECTOR_ENABLED = os.getenv("SLIME_ROLLOUT_COLLAPSE_DETECTOR", "1").lower() in ("1", "true", "yes")
COLLAPSE_WARN_SCORE = float(os.getenv("SLIME_ROLLOUT_COLLAPSE_WARN_SCORE", "0.5"))
COLLAPSE_CRITICAL_SCORE = float(os.getenv("SLIME_ROLLOUT_COLLAPSE_CRITICAL_SCORE", "1.0"))
COLLAPSE_MALFORMED_WARN_FRAC = float(os.getenv("SLIME_ROLLOUT_COLLAPSE_MALFORMED_WARN_FRAC", "0.10"))
COLLAPSE_MALFORMED_CRITICAL_FRAC = float(os.getenv("SLIME_ROLLOUT_COLLAPSE_MALFORMED_CRITICAL_FRAC", "0.25"))
COLLAPSE_MALFORMED_STOP_FRAC = float(os.getenv("SLIME_ROLLOUT_COLLAPSE_MALFORMED_STOP_FRAC", "0.30"))
COLLAPSE_RESPONSE_LEN_CRITICAL = float(os.getenv("SLIME_ROLLOUT_COLLAPSE_RESPONSE_LEN_CRITICAL", "120"))
COLLAPSE_BASELINE_WINDOW = int(os.getenv("SLIME_ROLLOUT_COLLAPSE_BASELINE_WINDOW", "50"))
COLLAPSE_PLOT_WINDOW = int(os.getenv("SLIME_ROLLOUT_COLLAPSE_PLOT_WINDOW", "200"))
COLLAPSE_EVENT_ROLLOUT_WINDOW = int(os.getenv("SLIME_ROLLOUT_COLLAPSE_EVENT_ROLLOUT_WINDOW", "5"))
COLLAPSE_EVENT_COOLDOWN_ROLLOUTS = int(os.getenv("SLIME_ROLLOUT_COLLAPSE_EVENT_COOLDOWN_ROLLOUTS", "5"))
ACTION_TOOL_RE = re.compile(
    r"(?:^|_)(delete|remove|send|post|publish|book|update|create|write|upload|share|transfer|purchase|submit)(?:_|$)",
    re.IGNORECASE,
)
READ_TOOL_RE = re.compile(r"(?:^|_)(get|list|read|search|fetch|retrieve|lookup|query)(?:_|$)", re.IGNORECASE)
_MONITOR_WRITE_LOCK = threading.Lock()

MALFORMED_PATTERNS = (
    # EOS emitted before an XML tag is closed.
    re.compile(r"</function\s*(?:<\|im_end\|>|$)"),
    re.compile(r"</parameter\s*(?:<\|im_end\|>|$)"),
    re.compile(r"<function=[^>\n]*(?:<\|im_end\|>|$)"),
    re.compile(r"<parameter=[^>\n]*(?:<\|im_end\|>|$)"),
    # Empty tool-call block followed by EOS.
    re.compile(r"<tool_call>\s*(?:<\|im_end\|>|$)"),
    # Common broken fragments observed during collapse.
    re.compile(r"</output>\s*(?:<\|im_end\|>|$)"),
    re.compile(r"</parameter>\s*</output>"),
    # Env feedback emitted after the SGLang parser rejects a malformed call.
    re.compile(r"could not be parsed into a valid tool call", re.IGNORECASE),
    re.compile(r"Use at most one tool call or provide a final answer", re.IGNORECASE),
)

MALFORMED_REASON_PATTERNS = (
    ("eos_inside_function_close", re.compile(r"</function\s*(?:<\|im_end\|>|$)")),
    ("eos_inside_parameter_close", re.compile(r"</parameter\s*(?:<\|im_end\|>|$)")),
    ("eos_inside_function_tag", re.compile(r"<function=[^>\n]*(?:<\|im_end\|>|$)")),
    ("eos_inside_parameter_value", re.compile(r"<parameter=[^>\n]*(?:<\|im_end\|>|$)")),
    ("eos_before_parameter_value", re.compile(r"<parameter=[^>]+>\s*(?:<\|im_end\|>|$)")),
    ("empty_tool_call_before_eos", re.compile(r"<tool_call>\s*(?:<\|im_end\|>|$)")),
    ("broken_output_tag", re.compile(r"</output>\s*(?:<\|im_end\|>|$)")),
    ("parameter_closed_by_output", re.compile(r"</parameter>\s*</output>")),
    ("parser_rejected_tool_like_output", re.compile(r"could not be parsed into a valid tool call", re.IGNORECASE)),
    ("parser_retry_instruction", re.compile(r"Use at most one tool call or provide a final answer", re.IGNORECASE)),
)


def _iter_samples(items: Any) -> Iterable[Any]:
    if isinstance(items, (list, tuple)):
        for item in items:
            yield from _iter_samples(item)
        return
    yield items


def _sample_metadata(sample: Any) -> dict[str, Any]:
    if isinstance(sample, dict):
        metadata = sample.get("metadata")
        if isinstance(metadata, dict):
            return metadata
        return sample
    metadata = getattr(sample, "metadata", None)
    return metadata if isinstance(metadata, dict) else {}


def _looks_like_unclosed_tool_call(text: str) -> bool:
    last_tool = text.rfind("<tool_call>")
    if last_tool < 0:
        return False
    tail = text[last_tool:]
    first_eos = min((tail.find(eos) for eos in EOS_MARKERS if eos in tail), default=-1)
    if first_eos < 0:
        return False
    before_eos = tail[:first_eos]
    return "</tool_call>" not in before_eos


def _is_malformed_tool_call(text: str) -> bool:
    if not text:
        return False
    if any(pattern.search(text) for pattern in MALFORMED_PATTERNS):
        return True
    return _looks_like_unclosed_tool_call(text)


def _malformed_reason(text: str) -> str | None:
    if not text:
        return None
    for reason, pattern in MALFORMED_REASON_PATTERNS:
        if pattern.search(text):
            return reason
    if _looks_like_unclosed_tool_call(text):
        return "unclosed_tool_call_before_eos"
    return None


def _has_parser_error_metadata(sample: Any) -> bool:
    metadata = _sample_metadata(sample)
    reward_breakdown = metadata.get("reward_breakdown") or {}
    env_metrics = metadata.get("env_metrics") or {}
    return (
        bool(reward_breakdown.get("parser_problem"))
        or reward_breakdown.get("source") == "parser_error"
        or bool(env_metrics.get("parser_problem"))
        or env_metrics.get("reward_source") == "parser_error"
    )


def _has_invalid_tool_call(sample: Any) -> bool:
    metadata = _sample_metadata(sample)
    env_metrics = metadata.get("env_metrics") or {}
    return (
        bool(env_metrics.get("invalid_tool_call_count"))
        or bool(env_metrics.get("undefined_tool_call_count"))
        or any((entry or {}).get("invalid_call") for entry in metadata.get("tool_history") or [])
    )


def _has_env_tool_execution_error(sample: Any) -> bool:
    metadata = _sample_metadata(sample)
    env_metrics = metadata.get("env_metrics") or {}
    return (
        bool(env_metrics.get("env_tool_execution_error"))
        or int(env_metrics.get("env_tool_execution_error_count") or 0) > 0
    )


def _has_judge_failure(sample: Any) -> bool:
    metadata = _sample_metadata(sample)
    reward_breakdown = metadata.get("reward_breakdown") or {}
    env_metrics = metadata.get("env_metrics") or {}
    judge_info = reward_breakdown.get("judge_info") or {}
    return (
        reward_breakdown.get("source") == "judge_failure_filter_pending"
        or bool(reward_breakdown.get("judge_failure"))
        or bool(env_metrics.get("judge_failure"))
        or bool(judge_info.get("judge_failure"))
    )


def _normalize_marker(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _is_malicious_query_metadata(metadata: dict[str, Any]) -> bool:
    task_metadata = metadata.get("task_metadata") or {}
    task_spec = metadata.get("task_spec") or {}
    if not isinstance(task_metadata, dict):
        task_metadata = {}
    if not isinstance(task_spec, dict):
        task_spec = {}
    nested_task_metadata = task_spec.get("task_metadata") or {}
    if not isinstance(nested_task_metadata, dict):
        nested_task_metadata = {}
    risk_spec = metadata.get("risk_spec") or task_spec.get("risk_spec") or {}
    if not isinstance(risk_spec, dict):
        risk_spec = {}

    metadata_sources = (task_metadata, nested_task_metadata)
    if any(bool(source.get("is_malicious_query_task")) for source in metadata_sources):
        return True
    task_ids = {_normalize_marker(source.get("task_id")) for source in metadata_sources}
    if any(task_id.startswith("querytarget") for task_id in task_ids):
        return True
    markers = {
        _normalize_marker(source.get(key))
        for source in metadata_sources
        for key in ("task_type", "harm_task_type", "safety_eval_family", "attack_name", "injection_surface")
    }
    for source in metadata_sources:
        benchmark_metadata = source.get("benchmark_metadata") or {}
        if isinstance(benchmark_metadata, dict):
            markers.add(_normalize_marker(benchmark_metadata.get("attack_name")))
            markers.add(_normalize_marker(benchmark_metadata.get("harm_task_type")))
            markers.add(_normalize_marker(benchmark_metadata.get("safety_eval_family")))
            markers.add(_normalize_marker(benchmark_metadata.get("injection_surface")))
    markers.add(_normalize_marker(risk_spec.get("goal_type")))
    return bool(markers & {"query_malicious_attack", "malicious_query", "query_target", "query"})


def _is_pure_malicious_sample(sample: Any) -> bool:
    metadata = getattr(sample, "metadata", None) or {}
    scenario = _normalize_marker(metadata.get("scenario"))
    return scenario in {"pure_malicious", "pure_attack", "malicious_only"} or _is_malicious_query_metadata(metadata)


def _sample_utility(sample: Any) -> float | None:
    metadata = getattr(sample, "metadata", None) or {}
    reward_breakdown = metadata.get("reward_breakdown") or {}
    value = reward_breakdown.get("utility_reward")
    if isinstance(value, (int, float, bool)):
        return float(value)
    evaluation = metadata.get("evaluation") or {}
    training_reward = evaluation.get("training_reward") or {}
    if isinstance(training_reward, dict):
        for key in ("raw_reward_after_cap", "raw_reward_before_cap", "reward"):
            value = training_reward.get(key)
            if isinstance(value, (int, float, bool)):
                return float(value)
    return None


def _sample_reward(sample: Any) -> float | None:
    value = getattr(sample, "reward", None)
    if isinstance(value, (int, float, bool)):
        return float(value)
    return None


def _sample_judge_safe(sample: Any) -> float | None:
    metadata = getattr(sample, "metadata", None) or {}
    reward_breakdown = metadata.get("reward_breakdown") or {}
    value = reward_breakdown.get("judge_safe")
    if isinstance(value, (int, float, bool)):
        return float(value)
    env_metrics = metadata.get("env_metrics") or {}
    value = env_metrics.get("judge_safe")
    if isinstance(value, (int, float, bool)):
        return float(value)
    return None


def _sample_scenario_marker(sample: Any) -> str:
    metadata = getattr(sample, "metadata", None) or {}
    return _normalize_marker(metadata.get("scenario"))


def _is_attacked_env_benign_sample(sample: Any) -> bool:
    scenario = _sample_scenario_marker(sample)
    return scenario in {"attacked", "attacked_env", "attack", "injected", "injection"} and not _is_pure_malicious_sample(sample)


def _sample_task_type(sample: Any) -> str:
    if _is_pure_malicious_sample(sample):
        return "pure"
    if _is_attacked_env_benign_sample(sample):
        return "attacked"
    return "clean"


def _sample_is_correct(sample: Any) -> bool | None:
    metadata = getattr(sample, "metadata", None) or {}
    evaluation = metadata.get("evaluation") or {}
    success = evaluation.get("success")
    if isinstance(success, bool):
        return success
    utility = _sample_utility(sample)
    if utility is None:
        return None
    return utility > 0


def _sample_is_safe(sample: Any) -> bool | None:
    judge_safe = _sample_judge_safe(sample)
    if judge_safe is None:
        return None
    return judge_safe >= 0.5


def _sample_group_key(args: Any, sample: Any) -> Any:
    group_index = getattr(sample, "group_index", None)
    if group_index is not None:
        return ("group_index", int(group_index))
    n_samples = int(getattr(args, "n_samples_per_prompt", 0) or 0)
    if n_samples > 0:
        return ("index_bucket", _sample_index(sample) // n_samples)
    return ("rollout", 0)


def _estimated_monitor_advantages(args: Any, samples: list[Any]) -> dict[int, float]:
    active = [sample for sample in samples if not bool(getattr(sample, "remove_sample", False))]
    groups: dict[Any, list[tuple[int, float]]] = {}
    for sample in active:
        reward = _sample_reward(sample)
        if reward is None:
            continue
        groups.setdefault(_sample_group_key(args, sample), []).append((id(sample), reward))

    advantages: dict[int, float] = {}
    for values in groups.values():
        rewards = [reward for _, reward in values]
        mean_reward = _mean(rewards)
        if mean_reward is None:
            continue
        variance = sum((reward - mean_reward) ** 2 for reward in rewards) / len(rewards)
        std = variance ** 0.5
        for sample_id, reward in values:
            advantages[sample_id] = (reward - mean_reward) / std if std > 1e-8 else 0.0
    return advantages


def _condition_summary(samples: list[Any], advantages: dict[int, float]) -> dict[str, float | int | None]:
    rewards = [reward for sample in samples for reward in [_sample_reward(sample)] if reward is not None]
    advs = [advantages[id(sample)] for sample in samples if id(sample) in advantages]
    return {
        "count": len(samples),
        "reward_mean": _mean(rewards),
        "advantage_mean": _mean(advs),
    }


def _task_condition_metrics(args: Any, flat_samples: list[Any]) -> dict[str, Any]:
    active = [sample for sample in flat_samples if not bool(getattr(sample, "remove_sample", False))]
    active_total = len(active)
    advantages = _estimated_monitor_advantages(args, active)
    by_type = {"clean": [], "attacked": [], "pure": []}
    for sample in active:
        by_type[_sample_task_type(sample)].append(sample)

    clean_correct = [sample for sample in by_type["clean"] if _sample_is_correct(sample) is True]
    clean_incorrect = [sample for sample in by_type["clean"] if _sample_is_correct(sample) is False]

    attacked_correct_safe = [
        sample
        for sample in by_type["attacked"]
        if _sample_is_correct(sample) is True and _sample_is_safe(sample) is True
    ]
    attacked_correct_unsafe = [
        sample
        for sample in by_type["attacked"]
        if _sample_is_correct(sample) is True and _sample_is_safe(sample) is False
    ]
    attacked_incorrect_safe = [
        sample
        for sample in by_type["attacked"]
        if _sample_is_correct(sample) is False and _sample_is_safe(sample) is True
    ]
    attacked_incorrect_unsafe = [
        sample
        for sample in by_type["attacked"]
        if _sample_is_correct(sample) is False and _sample_is_safe(sample) is False
    ]

    pure_safe = [sample for sample in by_type["pure"] if _sample_is_safe(sample) is True]
    pure_unsafe = [sample for sample in by_type["pure"] if _sample_is_safe(sample) is False]

    return {
        "advantage_note": "estimated_monitor_advantage_by_active_reward_group",
        "active_total": active_total,
        "task_mix": {
            task_type: {
                "count": len(samples),
                "frac": len(samples) / active_total if active_total else 0.0,
            }
            for task_type, samples in by_type.items()
        },
        "clean": {
            "correct": _condition_summary(clean_correct, advantages),
            "incorrect": _condition_summary(clean_incorrect, advantages),
        },
        "attacked": {
            "correct_safe": _condition_summary(attacked_correct_safe, advantages),
            "correct_unsafe": _condition_summary(attacked_correct_unsafe, advantages),
            "incorrect_safe": _condition_summary(attacked_incorrect_safe, advantages),
            "incorrect_unsafe": _condition_summary(attacked_incorrect_unsafe, advantages),
        },
        "pure": {
            "safe": _condition_summary(pure_safe, advantages),
            "unsafe": _condition_summary(pure_unsafe, advantages),
        },
    }


def _sample_index(sample: Any) -> int:
    value = getattr(sample, "index", None)
    return int(value or 0)


def _rollout_size(args: Any, flat_samples: list[Any]) -> int:
    rollout_batch_size = int(getattr(args, "rollout_batch_size", 0) or 0)
    n_samples = int(getattr(args, "n_samples_per_prompt", 0) or 0)
    configured = rollout_batch_size * n_samples
    return max(1, configured or len(flat_samples) or 1)


def _infer_rollout_id(args: Any, flat_samples: list[Any]) -> int:
    if not flat_samples:
        return 0
    return min(_sample_index(sample) for sample in flat_samples) // _rollout_size(args, flat_samples)


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _min(values: list[float]) -> float | None:
    return min(values) if values else None


def _max(values: list[float]) -> float | None:
    return max(values) if values else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    values = sorted(values)
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2


def _first_tool_name(sample: Any) -> str | None:
    metadata = getattr(sample, "metadata", None) or {}
    for entry in metadata.get("tool_history") or []:
        tool_name = (entry or {}).get("tool_name")
        if tool_name:
            return str(tool_name)
    match = re.search(r"<function=([^\s>]+)>", getattr(sample, "response", "") or "")
    return match.group(1) if match else None


def _tool_names(sample: Any) -> list[str]:
    metadata = getattr(sample, "metadata", None) or {}
    names = [str((entry or {}).get("tool_name")) for entry in metadata.get("tool_history") or [] if (entry or {}).get("tool_name")]
    if names:
        return names
    return [match.group(1) for match in re.finditer(r"<function=([^\s>]+)>", getattr(sample, "response", "") or "")]


def _is_action_tool(tool_name: str | None) -> bool:
    return bool(tool_name and ACTION_TOOL_RE.search(tool_name))


def _is_read_tool(tool_name: str | None) -> bool:
    return bool(tool_name and READ_TOOL_RE.search(tool_name))


def _response_len(sample: Any) -> int:
    value = getattr(sample, "response_length", None)
    if isinstance(value, (int, float, bool)) and int(value) > 0:
        return int(value)
    response = getattr(sample, "response", "") or ""
    return len(response.split())


def _json_default(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    return str(value)


def _sample_record(sample: Any, rollout_id: int, bucket: str, malformed_reason: str | None) -> dict[str, Any]:
    metadata = getattr(sample, "metadata", None) or {}
    env_metrics = metadata.get("env_metrics") or {}
    record = {
        "schema_version": 1,
        "created_at_unix": time.time(),
        "bucket": bucket,
        "rollout_id": rollout_id,
        "sample_index": getattr(sample, "index", None),
        "sample_group_index": getattr(sample, "group_index", None),
        "sample_session_id": getattr(sample, "session_id", None),
        "status": getattr(getattr(sample, "status", None), "value", str(getattr(sample, "status", None))),
        "task_id": metadata.get("task_id"),
        "scenario": metadata.get("scenario"),
        "domain": (metadata.get("task_metadata") or {}).get("domain"),
        "difficulty_tier": (metadata.get("task_metadata") or {}).get("difficulty_tier"),
        "episode_id": metadata.get("episode_id"),
        "user_query": metadata.get("user_query"),
        "available_tools": metadata.get("available_tools"),
        "response": getattr(sample, "response", ""),
        "response_length": _response_len(sample),
        "reward": _sample_reward(sample),
        "utility_reward": _sample_utility(sample),
        "judge_safe": _sample_judge_safe(sample),
        "malformed_reason": malformed_reason,
        "parser_problem": _has_parser_error_metadata(sample),
        "env_tool_execution_error": _has_env_tool_execution_error(sample),
        "invalid_tool_call": _has_invalid_tool_call(sample),
        "first_tool_name": _first_tool_name(sample),
        "first_tool_is_action": _is_action_tool(_first_tool_name(sample)),
        "tool_history": metadata.get("tool_history"),
        "step_rewards": metadata.get("step_rewards"),
        "evaluation": metadata.get("evaluation"),
        "reward_breakdown": metadata.get("reward_breakdown"),
        "env_metrics": env_metrics,
    }
    if MONITOR_INCLUDE_PROMPT:
        record["prompt"] = getattr(sample, "prompt", None)
    if MONITOR_INCLUDE_TOKENS:
        record["tokens"] = getattr(sample, "tokens", None)
        record["loss_mask"] = getattr(sample, "loss_mask", None)
    return record


def _write_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=_json_default))
        f.write("\n")


def _write_sample_record(base_dir: Path, record: dict[str, Any]) -> None:
    rollout_id = int(record["rollout_id"])
    sample_index = int(record.get("sample_index") or 0)
    bucket = str(record["bucket"])
    sample_dir = base_dir / "sample_buckets" / bucket
    sample_dir.mkdir(parents=True, exist_ok=True)
    sample_path = sample_dir / f"rollout_{rollout_id:06d}_sample_{sample_index:08d}.json"
    encoded = json.dumps(record, ensure_ascii=False, indent=2, default=_json_default)
    tmp_path = sample_path.with_suffix(f".json.tmp.{os.getpid()}")
    tmp_path.write_text(encoded + "\n", encoding="utf-8")
    tmp_path.replace(sample_path)
    _write_jsonl(base_dir / "sample_anomalies.jsonl", record)


def _read_json_file(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.exception("Failed to read JSON file: %s", path)
        return default


def _write_json_file(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}")
    tmp_path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=_json_default) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _read_jsonl_records(path: Path) -> list[dict[str, Any]]:
    records = []
    if not path.exists():
        return records
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
    except Exception:
        logger.exception("Failed to read JSONL file: %s", path)
    return records


def _metric_float(record: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = record.get(key)
    if isinstance(value, (int, float, bool)):
        return float(value)
    return default


def _severity_rank(level: str) -> int:
    return {"OK": 0, "WARN": 1, "CRITICAL": 2, "STOP_SUGGESTED": 3}.get(level, 0)


def _collapse_decision(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    current = metrics[-1]
    rollout_id = int(current.get("rollout_id") or 0)
    prior = [m for m in metrics[:-1] if int(m.get("rollout_id") or -1) < rollout_id]
    baseline_window = prior[-max(1, COLLAPSE_BASELINE_WINDOW):]
    baseline_values = [
        _metric_float(m, "utility_reward_mean")
        for m in baseline_window
        if m.get("utility_reward_mean") is not None
    ]
    current_utility = _metric_float(current, "utility_reward_mean")
    baseline_utility = _mean(baseline_values) if baseline_values else current_utility
    utility_drop = max(0.0, float(baseline_utility or 0.0) - current_utility)
    malformed_frac = _metric_float(current, "malformed_removed_frac")
    short_malformed_frac = _metric_float(current, "short_malformed_frac")
    negative_reward_frac = _metric_float(current, "negative_reward_frac")
    premature_eos_frac = _metric_float(current, "premature_eos_tool_call_frac")
    raw_reward_mean = _metric_float(current, "raw_reward_mean")
    response_len_mean = _metric_float(current, "response_len_mean", default=10**9)
    score = (
        3.0 * malformed_frac
        + 2.0 * short_malformed_frac
        + 1.5 * negative_reward_frac
        + utility_drop
        + 1.0 * premature_eos_frac
    )

    recent_2 = metrics[-2:]
    recent_3 = metrics[-3:]
    malformed_two_rounds = (
        len(recent_2) == 2
        and all(_metric_float(m, "malformed_removed_frac") > COLLAPSE_MALFORMED_WARN_FRAC for m in recent_2)
    )
    raw_reward_negative_three_rounds = (
        len(recent_3) == 3
        and all(_metric_float(m, "raw_reward_mean") < 0 for m in recent_3)
    )

    level = "OK"
    reasons = []
    if score >= COLLAPSE_WARN_SCORE:
        level = "WARN"
        reasons.append(f"collapse_score {score:.4f} >= warn threshold {COLLAPSE_WARN_SCORE:.4f}")
    if malformed_two_rounds:
        level = "WARN"
        reasons.append(
            f"malformed_removed_frac > {COLLAPSE_MALFORMED_WARN_FRAC:.4f} for two consecutive rollouts"
        )
    if score >= COLLAPSE_CRITICAL_SCORE:
        level = "CRITICAL"
        reasons.append(f"collapse_score {score:.4f} >= critical threshold {COLLAPSE_CRITICAL_SCORE:.4f}")
    if malformed_frac >= COLLAPSE_MALFORMED_CRITICAL_FRAC:
        level = "CRITICAL"
        reasons.append(
            f"malformed_removed_frac {malformed_frac:.4f} >= critical threshold {COLLAPSE_MALFORMED_CRITICAL_FRAC:.4f}"
        )
    if raw_reward_mean < 0:
        level = "CRITICAL"
        reasons.append(f"raw_reward_mean {raw_reward_mean:.4f} < 0")
    if response_len_mean < COLLAPSE_RESPONSE_LEN_CRITICAL and raw_reward_mean < 0:
        level = "CRITICAL"
        reasons.append(
            f"response_len_mean {response_len_mean:.4f} < {COLLAPSE_RESPONSE_LEN_CRITICAL:.4f} while reward is negative"
        )
    if malformed_frac >= COLLAPSE_MALFORMED_STOP_FRAC:
        level = "STOP_SUGGESTED"
        reasons.append(
            f"malformed_removed_frac {malformed_frac:.4f} >= stop threshold {COLLAPSE_MALFORMED_STOP_FRAC:.4f}"
        )
    if raw_reward_negative_three_rounds:
        level = "STOP_SUGGESTED"
        reasons.append("raw_reward_mean < 0 for three consecutive rollouts")

    return {
        "schema_version": 1,
        "created_at_unix": time.time(),
        "rollout_id": rollout_id,
        "level": level,
        "score": score,
        "reasons": reasons,
        "baseline_utility_reward_mean": baseline_utility,
        "current_utility_reward_mean": current_utility,
        "utility_drop": utility_drop,
        "current_metrics": current,
        "thresholds": {
            "warn_score": COLLAPSE_WARN_SCORE,
            "critical_score": COLLAPSE_CRITICAL_SCORE,
            "malformed_warn_frac": COLLAPSE_MALFORMED_WARN_FRAC,
            "malformed_critical_frac": COLLAPSE_MALFORMED_CRITICAL_FRAC,
            "malformed_stop_frac": COLLAPSE_MALFORMED_STOP_FRAC,
            "response_len_critical": COLLAPSE_RESPONSE_LEN_CRITICAL,
            "baseline_window": COLLAPSE_BASELINE_WINDOW,
        },
    }


def _svg_escape(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _write_collapse_svg(event_dir: Path, metrics: list[dict[str, Any]]) -> None:
    if not metrics:
        return
    series_defs = [
        ("raw_reward_mean", "raw reward", "#b91c1c", None),
        ("utility_reward_mean", "utility", "#2563eb", (0.0, 1.0)),
        ("judge_safe_mean", "judge safe", "#16a34a", (0.0, 1.0)),
        ("malformed_removed_frac", "malformed removed", "#9333ea", (0.0, 1.0)),
        ("short_malformed_frac", "short malformed", "#f97316", (0.0, 1.0)),
        ("premature_eos_tool_call_frac", "premature eos", "#0f766e", (0.0, 1.0)),
        ("negative_reward_frac", "negative reward frac", "#111827", (0.0, 1.0)),
        ("response_len_mean", "response len mean", "#64748b", None),
    ]
    width = 1200
    panel_h = 145
    left = 70
    right = 30
    top = 36
    bottom = 30
    height = top + bottom + panel_h * len(series_defs)
    x_values = [int(m.get("rollout_id") or i) for i, m in enumerate(metrics)]
    min_x = min(x_values)
    max_x = max(x_values)
    x_span = max(1, max_x - min_x)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{left}" y="24" font-family="monospace" font-size="16" fill="#111827">Rollout Collapse Detector Curves</text>',
    ]
    for panel_idx, (key, label, color, forced_range) in enumerate(series_defs):
        y0 = top + panel_idx * panel_h
        values = [_metric_float(m, key) for m in metrics if m.get(key) is not None]
        if not values:
            continue
        if forced_range:
            min_y, max_y = forced_range
        else:
            min_y, max_y = min(values), max(values)
            if min_y == max_y:
                pad = max(abs(min_y) * 0.1, 1.0)
                min_y -= pad
                max_y += pad
        y_span = max(1e-9, max_y - min_y)

        def point(metric: dict[str, Any], idx: int) -> str:
            x = left + ((int(metric.get("rollout_id") or idx) - min_x) / x_span) * (width - left - right)
            value = _metric_float(metric, key)
            y = y0 + 18 + (1.0 - ((value - min_y) / y_span)) * (panel_h - 42)
            return f"{x:.1f},{y:.1f}"

        polyline = " ".join(point(m, i) for i, m in enumerate(metrics) if m.get(key) is not None)
        parts.extend(
            [
                f'<line x1="{left}" y1="{y0 + panel_h - 22}" x2="{width - right}" y2="{y0 + panel_h - 22}" stroke="#e5e7eb"/>',
                f'<text x="10" y="{y0 + 24}" font-family="monospace" font-size="12" fill="{color}">{_svg_escape(label)}</text>',
                f'<text x="10" y="{y0 + 42}" font-family="monospace" font-size="10" fill="#6b7280">min={min_y:.3f} max={max_y:.3f}</text>',
                f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2"/>',
            ]
        )
    parts.append("</svg>")
    (event_dir / "collapse_curves.svg").write_text("\n".join(parts) + "\n", encoding="utf-8")


def _write_recent_anomalies(base_dir: Path, event_dir: Path, current_rollout_id: int) -> None:
    source = base_dir / "sample_anomalies.jsonl"
    target = event_dir / "recent_sample_anomalies.jsonl"
    if not source.exists():
        target.write_text("", encoding="utf-8")
        return
    min_rollout_id = current_rollout_id - max(1, COLLAPSE_EVENT_ROLLOUT_WINDOW) + 1
    with source.open("r", encoding="utf-8") as src, target.open("w", encoding="utf-8") as dst:
        for line in src:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if int(record.get("rollout_id") or -1) >= min_rollout_id:
                dst.write(json.dumps(record, ensure_ascii=False, default=_json_default))
                dst.write("\n")


def _write_collapse_report(event_dir: Path, decision: dict[str, Any], recent_metrics: list[dict[str, Any]]) -> None:
    current = decision.get("current_metrics") or {}
    reasons = decision.get("reasons") or []
    lines = [
        "# Rollout Collapse Detector Event",
        "",
        f"- level: `{decision.get('level')}`",
        f"- rollout_id: `{decision.get('rollout_id')}`",
        f"- score: `{float(decision.get('score') or 0.0):.6f}`",
        f"- baseline_utility_reward_mean: `{decision.get('baseline_utility_reward_mean')}`",
        f"- current_utility_reward_mean: `{decision.get('current_utility_reward_mean')}`",
        f"- utility_drop: `{decision.get('utility_drop')}`",
        "",
        "## Reasons",
    ]
    lines.extend(f"- {reason}" for reason in reasons)
    lines.extend(
        [
            "",
            "## Current Rollout Metrics",
            "",
            "```json",
            json.dumps(current, ensure_ascii=False, indent=2, default=_json_default),
            "```",
            "",
            "## What To Check Next",
            "",
            "- Inspect `recent_sample_anomalies.jsonl` for malformed XML, premature EOS, short responses, and negative-reward samples.",
            "- Inspect `collapse_curves.svg` for whether reward collapse coincides with malformed tool-call spikes.",
            "- Treat `STOP_SUGGESTED` as an advisory signal; this detector does not terminate training by itself.",
            "",
            f"Recent metrics included: `{len(recent_metrics)}` rollout rows.",
            "",
        ]
    )
    (event_dir / "collapse_report.md").write_text("\n".join(lines), encoding="utf-8")


def _maybe_run_collapse_detector(base_dir: Path, rollout_metrics: dict[str, Any]) -> None:
    if not COLLAPSE_DETECTOR_ENABLED:
        return
    metrics = _read_jsonl_records(base_dir / "rollout_metrics.jsonl")
    if not metrics:
        metrics = [rollout_metrics]
    decision = _collapse_decision(metrics)
    status_path = base_dir / "collapse_detector_status.json"
    state_path = base_dir / "collapse_detector_state.json"
    state = _read_json_file(state_path, {"events": []})
    current_rollout_id = int(decision["rollout_id"])
    level = str(decision["level"])
    status = {**decision, "event_written": False, "event_dir": None, "event_suppressed_by_cooldown": False}

    if level == "OK":
        _write_json_file(status_path, status)
        return

    last_event_rollout = int(state.get("last_event_rollout") or -10**9)
    last_event_level = str(state.get("last_event_level") or "OK")
    in_cooldown = current_rollout_id - last_event_rollout < COLLAPSE_EVENT_COOLDOWN_ROLLOUTS
    if in_cooldown and _severity_rank(level) <= _severity_rank(last_event_level):
        status["event_suppressed_by_cooldown"] = True
        _write_json_file(status_path, status)
        logger.warning(
            "Rollout collapse detector %s suppressed by cooldown at rollout_id=%s; score=%.4f reasons=%s",
            level,
            current_rollout_id,
            float(decision["score"]),
            decision["reasons"],
        )
        return

    event_name = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    event_dir = base_dir / "collapse_events" / f"event_{event_name}_rollout_{current_rollout_id:06d}_{level.lower()}"
    event_dir.mkdir(parents=True, exist_ok=True)
    recent_metrics = metrics[-max(1, COLLAPSE_PLOT_WINDOW):]
    _write_json_file(event_dir / "summary.json", decision)
    with (event_dir / "recent_rollout_metrics.jsonl").open("w", encoding="utf-8") as f:
        for record in recent_metrics:
            f.write(json.dumps(record, ensure_ascii=False, default=_json_default))
            f.write("\n")
    _write_recent_anomalies(base_dir, event_dir, current_rollout_id)
    _write_collapse_svg(event_dir, recent_metrics)
    _write_collapse_report(event_dir, decision, recent_metrics)
    status["event_written"] = True
    status["event_dir"] = str(event_dir)
    events = list(state.get("events") or [])
    events.append(
        {
            "created_at_unix": decision["created_at_unix"],
            "rollout_id": current_rollout_id,
            "level": level,
            "score": decision["score"],
            "event_dir": str(event_dir),
            "reasons": decision["reasons"],
        }
    )
    _write_json_file(
        state_path,
        {
            "last_event_rollout": current_rollout_id,
            "last_event_level": level,
            "events": events[-100:],
        },
    )
    _write_json_file(status_path, status)
    logger.warning(
        "Rollout collapse detector triggered %s at rollout_id=%s; score=%.4f; event_dir=%s; reasons=%s",
        level,
        current_rollout_id,
        float(decision["score"]),
        event_dir,
        decision["reasons"],
    )


def _bucket_sample(sample: Any, malformed_reason: str | None) -> list[str]:
    buckets = []
    reward = _sample_reward(sample)
    utility = _sample_utility(sample)
    judge_safe = _sample_judge_safe(sample)
    response_len = _response_len(sample)
    parser_problem = _has_parser_error_metadata(sample)
    env_error = _has_env_tool_execution_error(sample)
    judge_failure = _has_judge_failure(sample)
    invalid_tool = _has_invalid_tool_call(sample)
    if malformed_reason or parser_problem:
        buckets.append("malformed_or_parser_error")
    if judge_failure:
        buckets.append("judge_failure")
    if response_len < MONITOR_SHORT_RESPONSE_TOKENS:
        buckets.append("short_response")
    if response_len < MONITOR_SHORT_RESPONSE_TOKENS and (malformed_reason or parser_problem):
        buckets.append("short_malformed")
    if malformed_reason and malformed_reason.startswith("eos_"):
        buckets.append("premature_eos_tool_call")
    if reward is not None and reward < 0:
        buckets.append("negative_reward")
    if utility == 0 and judge_safe == 1:
        buckets.append("utility0_judge1")
    if utility == 1 and judge_safe == 0:
        buckets.append("utility1_judge0")
    if env_error:
        buckets.append("env_tool_execution_error")
    if invalid_tool:
        buckets.append("invalid_or_undefined_tool")
    first_tool = _first_tool_name(sample)
    if _is_action_tool(first_tool):
        buckets.append("action_first")
    return buckets


def _monitor_rollout_metrics(
    args: Any,
    flat_samples: list[Any],
    rollout_id: int,
    removed: int,
    rewards: list[Any],
    pure_updated: int,
    batch_stats: dict[str, float | int],
) -> dict[str, Any]:
    total = len(flat_samples)
    response_lengths = [_response_len(sample) for sample in flat_samples]
    rewards_numeric = [value for sample in flat_samples for value in [_sample_reward(sample)] if value is not None]
    utilities = [value for sample in flat_samples for value in [_sample_utility(sample)] if value is not None]
    judge_values = [value for sample in flat_samples for value in [_sample_judge_safe(sample)] if value is not None]
    malformed_reasons = [_malformed_reason(getattr(sample, "response", "") or "") for sample in flat_samples]
    parser_error_count = sum(1 for sample in flat_samples if _has_parser_error_metadata(sample))
    env_error_count = sum(1 for sample in flat_samples if _has_env_tool_execution_error(sample))
    judge_failure_count = sum(1 for sample in flat_samples if _has_judge_failure(sample))
    invalid_tool_count = sum(1 for sample in flat_samples if _has_invalid_tool_call(sample))
    short_response_count = sum(1 for length in response_lengths if length < MONITOR_SHORT_RESPONSE_TOKENS)
    short_malformed_count = sum(
        1
        for sample, reason in zip(flat_samples, malformed_reasons, strict=False)
        if _response_len(sample) < MONITOR_SHORT_RESPONSE_TOKENS and (reason or _has_parser_error_metadata(sample))
    )
    premature_eos_count = sum(1 for reason in malformed_reasons if reason and reason.startswith("eos_"))
    tool_names_by_sample = [_tool_names(sample) for sample in flat_samples]
    tool_counts = [len(names) for names in tool_names_by_sample]
    action_tool_counts = [sum(1 for name in names if _is_action_tool(name)) for names in tool_names_by_sample]
    read_tool_counts = [sum(1 for name in names if _is_read_tool(name)) for names in tool_names_by_sample]
    first_tool_names = [_first_tool_name(sample) for sample in flat_samples]
    action_first_count = sum(1 for name in first_tool_names if _is_action_tool(name))
    metadata_metrics = [(getattr(sample, "metadata", None) or {}).get("env_metrics") or {} for sample in flat_samples]
    hit_max_turns_count = sum(1 for metrics in metadata_metrics if bool(metrics.get("hit_max_turns")))
    truncated_count = sum(1 for sample in flat_samples if str(getattr(getattr(sample, "status", None), "value", "")).lower() == "truncated")
    negative_reward_count = sum(1 for value in rewards_numeric if value < 0)
    utility_zero_count = sum(1 for value in utilities if value == 0)
    utility_one_judge_zero_count = sum(
        1
        for sample in flat_samples
        if _sample_utility(sample) == 1 and _sample_judge_safe(sample) == 0
    )
    utility_zero_judge_one_count = sum(
        1
        for sample in flat_samples
        if _sample_utility(sample) == 0 and _sample_judge_safe(sample) == 1
    )
    task_condition_metrics = _task_condition_metrics(args, flat_samples)
    return {
        "schema_version": 1,
        "created_at_unix": time.time(),
        "rollout_id": rollout_id,
        "total_samples": total,
        "raw_reward_mean": _mean(rewards_numeric),
        "raw_reward_median": _median(rewards_numeric),
        "raw_reward_min": _min(rewards_numeric),
        "raw_reward_max": _max(rewards_numeric),
        "utility_reward_mean": _mean(utilities),
        "utility_reward_median": _median(utilities),
        "utility_zero_frac": utility_zero_count / total if total else 0.0,
        "judge_safe_mean": _mean(judge_values),
        "judge_safe_count": len(judge_values),
        "malformed_removed_count": removed,
        "malformed_removed_frac": removed / total if total else 0.0,
        "removed_rewards": rewards[:32],
        "parser_error_count": parser_error_count,
        "parser_error_frac": parser_error_count / total if total else 0.0,
        "env_tool_execution_error_count": env_error_count,
        "judge_failure_count": judge_failure_count,
        "judge_failure_frac": judge_failure_count / total if total else 0.0,
        "invalid_tool_call_count": invalid_tool_count,
        "response_len_mean": _mean([float(v) for v in response_lengths]),
        "response_len_median": _median([float(v) for v in response_lengths]),
        "response_len_min": min(response_lengths) if response_lengths else None,
        "response_len_max": max(response_lengths) if response_lengths else None,
        "short_response_threshold": MONITOR_SHORT_RESPONSE_TOKENS,
        "short_response_count": short_response_count,
        "short_response_frac": short_response_count / total if total else 0.0,
        "short_malformed_count": short_malformed_count,
        "short_malformed_frac": short_malformed_count / total if total else 0.0,
        "premature_eos_tool_call_count": premature_eos_count,
        "premature_eos_tool_call_frac": premature_eos_count / total if total else 0.0,
        "tool_call_count_mean": _mean([float(v) for v in tool_counts]),
        "action_tool_call_count_mean": _mean([float(v) for v in action_tool_counts]),
        "read_tool_call_count_mean": _mean([float(v) for v in read_tool_counts]),
        "action_first_tool_count": action_first_count,
        "action_first_tool_frac": action_first_count / total if total else 0.0,
        "hit_max_turns_count": hit_max_turns_count,
        "hit_max_turns_frac": hit_max_turns_count / total if total else 0.0,
        "truncated_count": truncated_count,
        "truncated_frac": truncated_count / total if total else 0.0,
        "negative_reward_count": negative_reward_count,
        "negative_reward_frac": negative_reward_count / total if total else 0.0,
        "utility1_judge0_count": utility_one_judge_zero_count,
        "utility0_judge1_count": utility_zero_judge_one_count,
        "pure_malicious_updated": pure_updated,
        "task_condition_metrics": task_condition_metrics,
        **batch_stats,
    }


def _save_monitor_outputs(args: Any, flat_samples: list[Any], rollout_metrics: dict[str, Any]) -> None:
    if not MONITOR_OUTPUT_DIR:
        return
    base_dir = Path(MONITOR_OUTPUT_DIR)
    rollout_id = int(rollout_metrics["rollout_id"])
    malformed_reasons = {
        id(sample): _malformed_reason(getattr(sample, "response", "") or "")
        for sample in flat_samples
    }
    try:
        with _MONITOR_WRITE_LOCK:
            base_dir.mkdir(parents=True, exist_ok=True)
            _write_jsonl(base_dir / "rollout_metrics.jsonl", rollout_metrics)
            if MONITOR_ENABLE_SAMPLE_BUCKETS:
                bucket_counts: dict[str, int] = {}
                normal_kept = 0
                for sample in sorted(flat_samples, key=_sample_index):
                    buckets = _bucket_sample(sample, malformed_reasons[id(sample)])
                    if not buckets and normal_kept < MONITOR_KEEP_NORMAL_SAMPLES:
                        buckets = ["normal_reference"]
                        normal_kept += 1
                    for bucket in buckets:
                        bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
                        if bucket_counts[bucket] > MONITOR_SAMPLE_MAX_PER_BUCKET:
                            continue
                        record = _sample_record(sample, rollout_id, bucket, malformed_reasons[id(sample)])
                        _write_sample_record(base_dir, record)
            _maybe_run_collapse_detector(base_dir, rollout_metrics)
    except Exception:
        logger.exception("Failed to save rollout monitor outputs for rollout_id=%s", rollout_id)


def _batch_reward_stats(flat_samples: list[Any]) -> dict[str, float | int]:
    active_samples = [sample for sample in flat_samples if not bool(getattr(sample, "remove_sample", False))]
    utilities = [
        utility
        for sample in active_samples
        if not _is_pure_malicious_sample(sample)
        for utility in [_sample_utility(sample)]
        if utility is not None
    ]
    judge_values = [
        judge_safe
        for sample in active_samples
        if not _is_pure_malicious_sample(sample)
        for judge_safe in [_sample_judge_safe(sample)]
        if judge_safe is not None
    ]
    judge_values_all = [
        judge_safe
        for sample in active_samples
        for judge_safe in [_sample_judge_safe(sample)]
        if judge_safe is not None
    ]
    return {
        "batch_utility_mean_non_pure": sum(utilities) / len(utilities) if utilities else BATCH_UTILITY_FALLBACK,
        "batch_utility_count_non_pure": len(utilities),
        "batch_judge_safe_mean_non_pure": sum(judge_values) / len(judge_values) if judge_values else -1.0,
        "batch_judge_safe_count_non_pure": len(judge_values),
        "batch_judge_safe_mean_all": sum(judge_values_all) / len(judge_values_all) if judge_values_all else -1.0,
        "batch_judge_safe_count_all": len(judge_values_all),
        "batch_pure_malicious_count": sum(1 for sample in active_samples if _is_pure_malicious_sample(sample)),
    }


def _attach_batch_stats(flat_samples: list[Any], stats: dict[str, float | int]) -> None:
    for sample in flat_samples:
        metadata = getattr(sample, "metadata", None) or {}
        task_category = _sample_task_type(sample)
        metadata["task_category"] = task_category
        env_metrics = metadata.setdefault("env_metrics", {})
        env_metrics.update(stats)
        env_metrics["task_category"] = task_category
        setattr(sample, "metadata", metadata)


def _apply_pure_malicious_batch_reward(flat_samples: list[Any]) -> tuple[int, dict[str, float | int]]:
    stats = _batch_reward_stats(flat_samples)
    _attach_batch_stats(flat_samples, stats)
    updated = 0
    for sample in flat_samples:
        if bool(getattr(sample, "remove_sample", False)):
            continue
        if not _is_pure_malicious_sample(sample):
            continue
        judge_safe = _sample_judge_safe(sample)
        if judge_safe is None:
            judge_safe = 0.0
        reward = float(judge_safe)
        setattr(sample, "reward", reward)
        metadata = getattr(sample, "metadata", None) or {}
        reward_breakdown = metadata.setdefault("reward_breakdown", {})
        reward_breakdown.update(
            {
                "source": "pure_malicious_judge_safe",
                "judge_safe": judge_safe,
                "reward_formula": "S",
            }
        )
        env_metrics = metadata.setdefault("env_metrics", {})
        env_metrics.update(stats)
        env_metrics["sample_reward"] = reward
        env_metrics["reward_source"] = reward_breakdown["source"]
        setattr(sample, "metadata", metadata)
        updated += 1
    return updated, stats


def filter_malformed_tool_calls(args, samples) -> None:
    """Mark malformed tool-call samples so slime excludes them from loss.

    ``samples`` is the rollout batch after generation. Depending on slime's
    grouping mode it can contain nested lists, so traversal is intentionally
    recursive.
    """

    flat_samples = list(_iter_samples(samples))
    rollout_id = _infer_rollout_id(args, flat_samples)
    total = 0
    removed = 0
    rewards = []
    for sample in flat_samples:
        response = getattr(sample, "response", "") or ""
        total += 1
        if (
            _has_parser_error_metadata(sample)
            or _has_env_tool_execution_error(sample)
            or _has_judge_failure(sample)
            or _is_malformed_tool_call(response)
        ):
            setattr(sample, "remove_sample", True)
            removed += 1
            rewards.append(getattr(sample, "reward", None))
    pure_updated, batch_stats = _apply_pure_malicious_batch_reward(flat_samples)
    batch_utility = float(batch_stats["batch_utility_mean_non_pure"])

    if total:
        rollout_metrics = _monitor_rollout_metrics(args, flat_samples, rollout_id, removed, rewards, pure_updated, batch_stats)
        _save_monitor_outputs(args, flat_samples, rollout_metrics)
        logger.info(
            "Malformed tool-call rollout filter removed %s/%s samples (%.3f); removed_rewards=%s; pure_malicious_updated=%s; batch_utility_mean_non_pure=%.6f; batch_utility_count_non_pure=%s; batch_judge_safe_mean_non_pure=%.6f; batch_judge_safe_count_non_pure=%s; batch_judge_safe_mean_all=%.6f; batch_judge_safe_count_all=%s; batch_pure_malicious_count=%s; judge_failure_count=%s; rollout_monitor=%s",
            removed,
            total,
            removed / total,
            rewards[:16],
            pure_updated,
            batch_utility,
            batch_stats["batch_utility_count_non_pure"],
            float(batch_stats["batch_judge_safe_mean_non_pure"]),
            batch_stats["batch_judge_safe_count_non_pure"],
            float(batch_stats["batch_judge_safe_mean_all"]),
            batch_stats["batch_judge_safe_count_all"],
            batch_stats["batch_pure_malicious_count"],
            rollout_metrics["judge_failure_count"],
            json.dumps(
                {
                    "rollout_id": rollout_id,
                    "raw_reward_mean": rollout_metrics["raw_reward_mean"],
                    "utility_reward_mean": rollout_metrics["utility_reward_mean"],
                    "judge_safe_mean": rollout_metrics["judge_safe_mean"],
                    "short_response_frac": rollout_metrics["short_response_frac"],
                    "short_malformed_frac": rollout_metrics["short_malformed_frac"],
                    "premature_eos_tool_call_frac": rollout_metrics["premature_eos_tool_call_frac"],
                    "negative_reward_frac": rollout_metrics["negative_reward_frac"],
                    "response_len_mean": rollout_metrics["response_len_mean"],
                    "action_first_tool_frac": rollout_metrics["action_first_tool_frac"],
                    "hit_max_turns_frac": rollout_metrics["hit_max_turns_frac"],
                    "task_condition_metrics": rollout_metrics["task_condition_metrics"],
                },
                ensure_ascii=False,
                default=_json_default,
            ),
        )
