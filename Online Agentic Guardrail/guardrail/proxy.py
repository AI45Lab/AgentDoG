"""Guardrail proxy — wraps openclaw agent with PRE_REPLY interception.

This is the integration layer that makes guardrail work in CLI mode.
It sits between the user and openclaw, intercepting every agent response:

    User → guardrail proxy → openclaw agent → session_events
                ↑                                    ↓
                └──── guardrail service ←────────────┘
                      (safe? deliver / unsafe? block)

Usage:
    # Instead of:
    openclaw agent --message "do something" --json

    # Use:
    python -m guardrail proxy --message "do something"

    # Or start as a persistent proxy server that wraps openclaw:
    python -m guardrail proxy-serve --port 8341

The proxy:
    1. Forwards the request to openclaw agent
    2. Captures the session events
    3. POSTs to guardrail service for evaluation
    4. If safe → returns openclaw's response
    5. If unsafe → blocks, returns warning
"""

from __future__ import annotations

import json
import glob
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any


def proxy_agent_call(
    message: str,
    guardrail_url: str = "http://127.0.0.1:8340",
    session_id: str | None = None,
    agent: str = "main",
    timeout: int = 120,
    openclaw_prefix: str = "",
    sessions_dir: str = "",
) -> dict[str, Any]:
    """Execute openclaw agent call with guardrail interception.

    Returns:
        {
            "blocked": bool,
            "guardrail": {"prediction": 0|1|-1, "label": "...", "reason": "..."},
            "agent_response": {...} or None if blocked,
            "raw_stdout": str,
        }
    """
    sid = session_id or f"guardrail-{int(time.time() * 1000)}"
    sessions_path = _resolve_sessions_dir(sessions_dir)

    # Record files before
    before_files = set(glob.glob(str(sessions_path / "*.jsonl")))
    before_mtimes = {f: os.path.getmtime(f) for f in before_files}
    start_time = time.time()

    # Build and run openclaw command
    cmd = f"openclaw agent --session-id {sid} --agent {agent} --message {_shell_quote(message)} --json --timeout {timeout}"
    if openclaw_prefix:
        cmd = f"{openclaw_prefix} {_shell_quote(cmd)}"

    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout + 30,
        )
        raw_stdout = result.stdout
        raw_stderr = result.stderr
    except subprocess.TimeoutExpired:
        return {
            "blocked": False,
            "guardrail": {"prediction": -1, "label": "error", "reason": "Agent timeout"},
            "agent_response": None,
            "raw_stdout": "",
        }

    # Find the session events (new file or modified file)
    time.sleep(0.5)
    session_events_text = _find_session_events(
        sessions_path, before_files, before_mtimes, start_time,
    )

    if not session_events_text:
        # No events captured — can't evaluate, fail-open
        return {
            "blocked": False,
            "guardrail": {"prediction": -1, "label": "error", "reason": "No session events captured"},
            "agent_response": _parse_agent_response(raw_stdout),
            "raw_stdout": raw_stdout,
        }

    # POST to guardrail service
    guardrail_result = _check_guardrail(session_events_text, guardrail_url)

    blocked = guardrail_result.get("prediction") == 1

    return {
        "blocked": blocked,
        "guardrail": guardrail_result,
        "agent_response": None if blocked else _parse_agent_response(raw_stdout),
        "raw_stdout": "" if blocked else raw_stdout,
    }


def _resolve_sessions_dir(custom: str = "") -> Path:
    if custom:
        p = custom.replace("~", str(Path.home()))
        return Path(p)
    return Path.home() / ".openclaw/agents/main/sessions"


def _find_session_events(
    sessions_path: Path,
    before_files: set[str],
    before_mtimes: dict[str, float],
    start_time: float,
) -> str:
    """Find session events created or modified since the agent call."""
    after_files = set(glob.glob(str(sessions_path / "*.jsonl")))

    # New files first
    new_files = after_files - before_files
    if new_files:
        # Use the newest
        newest = max(new_files, key=lambda f: os.path.getmtime(f))
        return Path(newest).read_text(encoding="utf-8")

    # Check modified files
    for f in after_files:
        mtime = os.path.getmtime(f)
        if mtime > before_mtimes.get(f, 0):
            text = Path(f).read_text(encoding="utf-8")
            # Filter to recent events only
            return _filter_recent_events(text, start_time)

    return ""


def _filter_recent_events(text: str, start_time: float) -> str:
    """Keep only events from after start_time."""
    from datetime import datetime
    cutoff = start_time - 5  # 5s grace

    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            event = json.loads(stripped)
            ts = event.get("timestamp", "")
            if ts:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if dt.timestamp() >= cutoff:
                    lines.append(stripped)
            else:
                lines.append(stripped)
        except json.JSONDecodeError:
            continue
    return "\n".join(lines)


def _check_guardrail(session_events_text: str, guardrail_url: str) -> dict[str, Any]:
    """POST session events to guardrail service."""
    try:
        body = json.dumps({"session_events": session_events_text}).encode("utf-8")
        req = urllib.request.Request(
            f"{guardrail_url.rstrip('/')}/check",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {
            "prediction": -1,
            "label": "error",
            "reason": f"Guardrail service error: {exc}",
        }


def _parse_agent_response(stdout: str) -> dict[str, Any] | None:
    """Extract JSON response from openclaw agent stdout."""
    if not stdout.strip():
        return None
    decoder = json.JSONDecoder()
    for i in range(len(stdout) - 1, -1, -1):
        if stdout[i] in "{}":
            for j in range(i):
                if stdout[j] == "{":
                    try:
                        data, end = decoder.raw_decode(stdout[j:])
                        return data
                    except json.JSONDecodeError:
                        continue
    return None


def _shell_quote(s: str) -> str:
    """Simple shell quoting."""
    import shlex
    return shlex.quote(s)


def run_proxy_cli(
    message: str,
    guardrail_url: str = "http://127.0.0.1:8340",
    agent: str = "main",
    timeout: int = 120,
) -> int:
    """CLI entry point for proxy mode. Returns exit code."""
    print(f"[GUARDRAIL PROXY] Evaluating agent response...", file=sys.stderr)

    result = proxy_agent_call(
        message=message,
        guardrail_url=guardrail_url,
        agent=agent,
        timeout=timeout,
        openclaw_prefix="zsh -i -c",
    )

    guardrail = result["guardrail"]
    label = guardrail.get("label", "?").upper()
    reason = guardrail.get("reason", "")

    if result["blocked"]:
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"GUARDRAIL BLOCKED — UNSAFE trajectory detected", file=sys.stderr)
        print(f"Reason: {reason}", file=sys.stderr)
        print(f"The agent's response has been suppressed.", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)
        return 1
    else:
        print(f"[GUARDRAIL PROXY] {label}: {reason}", file=sys.stderr)
        # Output the agent's original response
        if result["raw_stdout"]:
            print(result["raw_stdout"])
        return 0
