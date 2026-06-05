from __future__ import annotations

import json
from typing import Any


def extract_trajectory_text(session_events_text: str) -> str:
    """Parse session_events JSONL and format a readable trajectory.

    Only processes "message" type events. Skips metadata events
    (session, model_change, thinking_level_change, custom).
    """
    if not session_events_text or not session_events_text.strip():
        return ""

    blocks: list[str] = []
    for line in session_events_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "message":
            continue
        block = _format_message_event(event)
        if block:
            blocks.append(block)

    return "\n\n".join(blocks)


def extract_tool_list(session_events_text: str) -> list[str]:
    """Extract deduplicated sorted list of tool names from session events."""
    if not session_events_text or not session_events_text.strip():
        return []

    tools: set[str] = set()
    for line in session_events_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "message":
            continue
        message = event.get("message")
        if not isinstance(message, dict):
            continue

        # From toolResult events
        tool_name = message.get("toolName")
        if isinstance(tool_name, str) and tool_name:
            tools.add(tool_name)

        # From assistant toolCall content items
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "toolCall":
                    name = item.get("name")
                    if isinstance(name, str) and name:
                        tools.add(name)

    return sorted(tools)


def _format_message_event(event: dict[str, Any]) -> str:
    timestamp = event.get("timestamp", "")
    message = event.get("message")
    if not isinstance(message, dict):
        return ""

    role = message.get("role", "")
    content = message.get("content")
    parts: list[str] = []

    if role == "user":
        text = _extract_text_from_content(content)
        if text:
            parts.append(f"[{timestamp}] USER:\n{text}")

    elif role == "assistant":
        thinking_parts: list[str] = []
        text_parts: list[str] = []
        tool_parts: list[str] = []

        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "thinking":
                    t = item.get("thinking", "")
                    if t:
                        thinking_parts.append(t)
                elif item.get("type") == "text":
                    t = item.get("text", "")
                    if t:
                        text_parts.append(t)
                elif item.get("type") == "toolCall":
                    name = item.get("name", "?")
                    args = item.get("arguments", {})
                    args_str = json.dumps(args, ensure_ascii=False) if isinstance(args, dict) else str(args)
                    tool_parts.append(f"[TOOL_CALL: {name}] {args_str}")

        header = f"[{timestamp}] ASSISTANT:"
        body_lines: list[str] = []
        if thinking_parts:
            body_lines.append("[THINKING] " + "\n".join(thinking_parts))
        if text_parts:
            body_lines.append("\n".join(text_parts))
        if tool_parts:
            body_lines.extend(tool_parts)

        if body_lines:
            parts.append(header + "\n" + "\n".join(body_lines))

    elif role == "toolResult":
        tool_name = message.get("toolName", "?")
        is_error = message.get("isError", False)
        text = _extract_text_from_content(content)
        error_tag = " [ERROR]" if is_error else ""
        header = f"[{timestamp}] TOOL_RESULT ({tool_name}){error_tag}:"
        if text:
            parts.append(f"{header}\n{text}")
        else:
            parts.append(f"{header}\n(no output)")

    return "\n".join(parts)


def _extract_text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                t = item.get("text", "")
                if t:
                    texts.append(t)
            elif isinstance(item, str):
                texts.append(item)
        return "\n".join(texts)
    return ""
