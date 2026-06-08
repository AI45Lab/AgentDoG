from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from guardrail.config import GuardrailConfig
from guardrail.prompt import AGENTDOG_TRAJ_PROMPT
from guardrail.trajectory import extract_tool_list, extract_trajectory_text


@dataclass(frozen=True)
class GuardrailResult:
    prediction: int  # 0=safe, 1=unsafe, -1=error
    reason: str
    raw_response: str
    model: str
    error: str | None


def evaluate(session_events_text: str, config: GuardrailConfig) -> GuardrailResult:
    """Evaluate trajectory safety using the guardrail model.

    Returns GuardrailResult with prediction:
      0 = safe, 1 = unsafe, -1 = guardrail error (non-blocking).
    """
    trajectory = extract_trajectory_text(session_events_text)
    if not trajectory:
        return GuardrailResult(
            prediction=0,
            reason="No trajectory data available",
            raw_response="",
            model=config.model,
            error=None,
        )

    tool_list = extract_tool_list(session_events_text)
    tool_list_text = ", ".join(tool_list) if tool_list else "(none)"

    prompt = AGENTDOG_TRAJ_PROMPT.format(
        trajectory=trajectory,
        tool_list_text=tool_list_text,
    )

    try:
        raw_response = _call_api(prompt, config)
    except Exception as exc:
        return GuardrailResult(
            prediction=-1,
            reason=f"API call failed: {exc}",
            raw_response="",
            model=config.model,
            error=str(exc),
        )

    try:
        content = _extract_content(raw_response)
        pred, reason = _parse_response(content)
    except Exception as exc:
        return GuardrailResult(
            prediction=-1,
            reason=f"Response parsing failed: {exc}",
            raw_response=json.dumps(raw_response, ensure_ascii=False) if isinstance(raw_response, dict) else str(raw_response),
            model=config.model,
            error=str(exc),
        )

    return GuardrailResult(
        prediction=pred,
        reason=reason,
        raw_response=json.dumps(raw_response, ensure_ascii=False) if isinstance(raw_response, dict) else str(raw_response),
        model=config.model,
        error=None,
    )


def _call_api(prompt: str, config: GuardrailConfig) -> dict[str, Any]:
    """Call the OpenAI-compatible chat completions API via newapi."""
    url = f"{config.api_base.rstrip('/')}/chat/completions"
    body = json.dumps(
        {
            "model": config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 1,
            "max_tokens": 2048,
        }
    ).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.api_key}",
    }

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=config.timeout_seconds) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_content(response: dict[str, Any]) -> str:
    """Extract the assistant message content from API response."""
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("No choices in API response")
    message = choices[0].get("message")
    if not isinstance(message, dict):
        raise ValueError("No message in first choice")
    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("No content in message")
    return content


def _parse_response(content: str) -> tuple[int, str]:
    """Parse {pred, reason} JSON from model response.

    Handles markdown code fence wrapping.
    """
    text = content.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n", 1)
        text = lines[1] if len(lines) > 1 else text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}")

    pred = int(data["pred"])
    if pred not in (0, 1):
        raise ValueError(f"pred must be 0 or 1, got {pred}")

    reason = str(data.get("reason", ""))
    return pred, reason
