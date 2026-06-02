import copy
import json
import os
import re


DEFAULT_REPETITION_CAP = 0.2
DEFAULT_MAX_REPEATED_TOOL_ARGS = 2
DEFAULT_MAX_RESPONSE_CHARS = 12000

TOOL_ERROR_PATTERNS = (
    "tool execution failed",
    "tool runtime error",
    "tool contract failed",
    "tool source validation failed",
    "unhandled server tool error",
    "typeerror:",
    "traceback",
)


def final_success_only_reward_enabled():
    return str(os.getenv("TASKSVC_FINAL_SUCCESS_ONLY_REWARD", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _json_key(value):
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        return str(value)


def _tool_call_signature(history_item):
    return (
        str((history_item or {}).get("tool_name") or ""),
        _json_key((history_item or {}).get("arguments") or {}),
    )


def _resource_progress_from_episode(episode):
    for container in (
        episode.get("checklist_scores"),
        episode.get("evaluation", {}).get("checklist_scores") if isinstance(episode.get("evaluation"), dict) else None,
    ):
        if isinstance(container, dict):
            try:
                return float(container.get("subgoal_progress") or 0.0)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


def _has_tool_runtime_error(history):
    for item in history or []:
        reward_info = (item or {}).get("reward_info") or {}
        error_type = str(reward_info.get("error_type") or "").lower()
        if error_type and error_type not in {"none", "null"}:
            return True
        observation = str((item or {}).get("observation") or "").lower()
        if any(pattern in observation for pattern in TOOL_ERROR_PATTERNS):
            return True
    return False


def _max_repeated_tool_args(history):
    counts = {}
    max_count = 0
    for item in history or []:
        signature = _tool_call_signature(item)
        if not signature[0]:
            continue
        counts[signature] = counts.get(signature, 0) + 1
        max_count = max(max_count, counts[signature])
    return max_count


def compute_training_reward(
    episode,
    *,
    final_answer=None,
    truncated=False,
    max_repeated_tool_args=DEFAULT_MAX_REPEATED_TOOL_ARGS,
    max_response_chars=DEFAULT_MAX_RESPONSE_CHARS,
    repetition_cap=DEFAULT_REPETITION_CAP,
):
    """Compute the RL-facing reward from final outcome plus health gates.

    Checklist progress remains diagnostic only. Health gates prevent episodes
    with repeated calls, truncation, or server/tool errors from receiving a high
    reward even when a final state rule happens to pass.
    """

    episode = copy.deepcopy(episode or {})
    history = list(episode.get("history") or [])
    final_success = bool(episode.get("success"))
    answer = final_answer if final_answer is not None else episode.get("final_answer")
    answer = "" if answer is None else str(answer)

    raw_before = 1.0 if final_success else 0.0
    max_repeat = _max_repeated_tool_args(history)
    repetition_penalty = max_repeat > int(max_repeated_tool_args)
    truncation_penalty = bool(truncated) or str(episode.get("finish_reason") or "").lower() in {
        "max_turns_exhausted",
        "truncated",
        "max_tokens",
    }
    response_length_penalty = len(answer) > int(max_response_chars)
    tool_error_penalty = _has_tool_runtime_error(history)

    if final_success_only_reward_enabled():
        return {
            "final_success": final_success,
            "resource_progress": _resource_progress_from_episode(episode),
            "repetition_penalty": repetition_penalty,
            "truncation_penalty": truncation_penalty,
            "tool_error_penalty": tool_error_penalty,
            "response_length_penalty": response_length_penalty,
            "max_repeated_tool_args": max_repeat,
            "response_chars": len(answer),
            "raw_reward_before_cap": raw_before,
            "raw_reward_after_cap": raw_before,
            "cap_reasons": [],
            "reward_mode": "final_success_only",
        }

    cap_reasons = []
    reward = raw_before
    if not final_success:
        cap_reasons.append("final_failure")
        reward = 0.0
    if final_success and (truncation_penalty or tool_error_penalty):
        if truncation_penalty:
            cap_reasons.append("truncated")
        if tool_error_penalty:
            cap_reasons.append("tool_runtime_error")
        reward = 0.0
    if final_success and not (truncation_penalty or tool_error_penalty) and (repetition_penalty or response_length_penalty):
        if repetition_penalty:
            cap_reasons.append("repeated_tool_args")
        if response_length_penalty:
            cap_reasons.append("response_too_long")
        reward = min(float(repetition_cap), reward)

    return {
        "final_success": final_success,
        "resource_progress": _resource_progress_from_episode(episode),
        "repetition_penalty": repetition_penalty,
        "truncation_penalty": truncation_penalty,
        "tool_error_penalty": tool_error_penalty,
        "response_length_penalty": response_length_penalty,
        "max_repeated_tool_args": max_repeat,
        "response_chars": len(answer),
        "raw_reward_before_cap": raw_before,
        "raw_reward_after_cap": float(reward),
        "cap_reasons": cap_reasons,
    }
