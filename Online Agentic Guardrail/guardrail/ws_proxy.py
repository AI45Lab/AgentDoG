"""WebSocket proxy for PRE_REPLY guardrail interception.

Sits between OpenClaw TUI and Gateway. Buffers agent stream events,
evaluates the complete trajectory when the reply is done, and either
forwards the original or replaces with a guardrail block message.

Usage:
    python3 -m guardrail ws-proxy --port 18790
    openclaw tui --url ws://127.0.0.1:18790 --token <token>
"""

from __future__ import annotations

import asyncio
import copy
import json
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunBuffer:
    """Buffer events for one agent run until evaluation completes."""
    run_id: str
    user_message: str = ""
    buffered_raw: list[str] = field(default_factory=list)
    trajectory_lines: list[str] = field(default_factory=list)
    final_raw: str | None = None
    final_parsed: dict | None = None


async def run_proxy(
    listen_host: str = "127.0.0.1",
    listen_port: int = 18790,
    gateway_url: str = "ws://127.0.0.1:18789",
    guardrail_url: str = "http://127.0.0.1:8340",
) -> None:
    try:
        from websockets.asyncio.server import serve
        from websockets.asyncio.client import connect
    except ImportError:
        print("[GUARDRAIL-PROXY] Error: pip install websockets", file=sys.stderr)
        return

    log(f"Listening on ws://{listen_host}:{listen_port}")
    log(f"Gateway: {gateway_url}")
    log(f"Guardrail: {guardrail_url}")

    async def handle_client(client_ws):
        log("TUI connected")

        # Wait for TUI's first message to get auth params, then connect to gateway
        # Gateway expects: TUI connects → GW sends challenge → TUI sends connect with token
        # We connect to gateway first with the same URL, then relay everything

        # Read gateway token from config for the proxy→gateway connection
        gw_token = _read_gateway_token()
        gw_url_with_auth = gateway_url
        if gw_token:
            sep = "&" if "?" in gateway_url else "?"
            gw_url_with_auth = f"{gateway_url}{sep}auth.token={gw_token}"

        try:
            gw_ws = await connect(gw_url_with_auth, open_timeout=10)
        except Exception as exc:
            log(f"Gateway connect failed: {exc}")
            await client_ws.close(1011, "Gateway unavailable")
            return
        log("Connected to gateway")

        active_runs: dict[str, RunBuffer] = {}
        pending_run_id: str | None = None  # runId from chat.send response

        async def tui_to_gateway():
            nonlocal pending_run_id
            try:
                async for raw in client_ws:
                    text = raw if isinstance(raw, str) else raw.decode("utf-8")
                    try:
                        msg = json.loads(text)
                    except json.JSONDecodeError:
                        await gw_ws.send(raw)
                        continue

                    method = msg.get("method", "")
                    if method == "chat.send":
                        params = msg.get("params", {})
                        user_msg = params.get("message", "")
                        log(f"User: {user_msg[:80]}")
                        pending_run_id = f"pending:{msg.get('id', '')}"
                        active_runs[pending_run_id] = RunBuffer(
                            run_id=pending_run_id,
                            user_message=user_msg,
                        )
                        active_runs[pending_run_id].trajectory_lines.append(
                            f"[USER] {user_msg[:1000]}"
                        )

                    await gw_ws.send(raw)
            except Exception as exc:
                log(f"TUI→GW error: {exc}")
            finally:
                await gw_ws.close()

        async def gateway_to_tui():
            nonlocal pending_run_id
            try:
                async for raw in gw_ws:
                    text = raw if isinstance(raw, str) else raw.decode("utf-8")
                    try:
                        msg = json.loads(text)
                    except json.JSONDecodeError:
                        await client_ws.send(raw)
                        continue

                    # Response to chat.send — contains runId
                    if "ok" in msg and pending_run_id and pending_run_id.startswith("pending:"):
                        msg_id = str(msg.get("id", ""))
                        expected_id = pending_run_id.split(":", 1)[1]
                        if msg_id == expected_id:
                            payload = msg.get("payload", {})
                            run_id = payload.get("runId", "")
                            if run_id:
                                # Move buffer from pending to actual runId
                                buf = active_runs.pop(pending_run_id, None)
                                if buf:
                                    buf.run_id = run_id
                                    active_runs[run_id] = buf
                                    log(f"Tracking run: {run_id[:20]}")
                            pending_run_id = None
                        await client_ws.send(raw)
                        continue

                    # Event messages
                    event_name = msg.get("event", "")
                    payload = msg.get("payload", {}) if isinstance(msg.get("payload"), dict) else {}
                    run_id = payload.get("runId", "")

                    # Agent stream events — buffer if we're tracking this run
                    if event_name == "agent" and run_id and run_id in active_runs:
                        buf = active_runs[run_id]
                        buf.buffered_raw.append(text)

                        # Extract trajectory info from stream data
                        data = payload.get("data", {})
                        if isinstance(data, dict):
                            stream_text = data.get("text", "")
                            stream_type = data.get("type", "")
                            # Collect the latest full text for trajectory
                            if stream_text:
                                # Update trajectory with latest accumulated text
                                buf._last_stream_text = stream_text
                        continue  # Don't forward yet

                    # Chat events — buffer deltas, intercept final
                    if event_name == "chat" and run_id and run_id in active_runs:
                        buf = active_runs[run_id]
                        state = payload.get("state", "")

                        if state == "delta":
                            buf.buffered_raw.append(text)
                            # Extract full content from delta for trajectory
                            message = payload.get("message", {})
                            if isinstance(message, dict):
                                role = message.get("role", "")
                                content = message.get("content", [])
                                if role == "assistant":
                                    _collect_trajectory_from_content(buf, content)
                                elif role == "toolResult":
                                    tool_name = message.get("toolName", "?")
                                    result_text = _extract_text_only(content)
                                    is_error = message.get("isError", False)
                                    tag = f" [ERROR]" if is_error else ""
                                    buf.trajectory_lines.append(
                                        f"[TOOL_RESULT: {tool_name}{tag}] {result_text[:500]}"
                                    )
                            continue  # Don't forward yet

                        if state == "final":
                            buf.final_raw = text
                            buf.final_parsed = msg

                            # Extract final content for trajectory
                            message = payload.get("message", {})
                            content = message.get("content", [])
                            role = message.get("role", "")
                            if role == "assistant":
                                _collect_trajectory_from_content(buf, content)
                            reply_text = _extract_text(content)

                            # ---- EVALUATE ----
                            trajectory = "\n\n".join(buf.trajectory_lines)
                            log(f"Evaluating ({len(buf.trajectory_lines)} lines, {len(trajectory)} chars)")

                            eval_result = await _evaluate_async(
                                trajectory, guardrail_url
                            )
                            label = eval_result.get("label", "?")
                            reason = eval_result.get("reason", "")
                            log(f"Verdict: {label} — {reason[:100]}")

                            if eval_result.get("prediction") == 1:
                                # UNSAFE — send only a replaced final event
                                log(">>> REPLY BLOCKED <<<")
                                block_event = _make_block_event(
                                    msg, reason, reply_text
                                )
                                await client_ws.send(json.dumps(block_event))
                            else:
                                # SAFE — flush all buffered events + final
                                for buffered in buf.buffered_raw:
                                    await client_ws.send(buffered)
                                await client_ws.send(text)

                            del active_runs[run_id]
                            continue

                    # All other events (health, tick, connect, etc) — forward immediately
                    await client_ws.send(raw if isinstance(raw, (str, bytes)) else text)

            except Exception as exc:
                log(f"GW→TUI error: {exc}")
            finally:
                await client_ws.close()

        tui_task = asyncio.create_task(tui_to_gateway())
        gw_task = asyncio.create_task(gateway_to_tui())
        done, pending = await asyncio.wait(
            [tui_task, gw_task], return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        log("Session ended")

    async with serve(handle_client, listen_host, listen_port):
        log("Proxy ready, waiting for TUI connections...")
        await asyncio.Future()


def _collect_trajectory_from_content(buf: RunBuffer, content: Any) -> None:
    """Extract thinking, toolCall, text from content array into trajectory."""
    if not isinstance(content, list):
        return
    for item in content:
        if not isinstance(item, dict):
            continue
        ctype = item.get("type", "")
        if ctype == "thinking" and item.get("thinking"):
            line = f"[THINKING] {item['thinking'][:1000]}"
            if line not in buf.trajectory_lines:
                buf.trajectory_lines.append(line)
        elif ctype == "toolCall":
            name = item.get("name", "?")
            args = json.dumps(item.get("arguments", {}), ensure_ascii=False)[:500]
            line = f"[TOOL_CALL: {name}] {args}"
            if line not in buf.trajectory_lines:
                buf.trajectory_lines.append(line)
        elif ctype == "text" and item.get("text"):
            line = f"[ASSISTANT] {item['text'][:1000]}"
            # Only keep the latest text (deltas are cumulative)
            buf.trajectory_lines = [
                l for l in buf.trajectory_lines if not l.startswith("[ASSISTANT]")
            ]
            buf.trajectory_lines.append(line)


def _extract_text(content: Any) -> str:
    """Extract all readable text from message content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text" and item.get("text"):
                    texts.append(item["text"])
                elif item.get("type") == "thinking" and item.get("thinking"):
                    texts.append(f"[THINKING] {item['thinking']}")
        return "\n".join(texts)
    return ""


def _extract_text_only(content: Any) -> str:
    """Extract only text type content (no thinking)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            item["text"] for item in content
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text")
        )
    return ""


def _make_block_event(original_final: dict, reason: str, original_text: str) -> dict:
    """Create a replacement chat final event with guardrail block message."""
    blocked = copy.deepcopy(original_final)
    block_text = (
        f"[GUARDRAIL] This reply has been blocked by the PRE_REPLY safety guardrail.\n"
        f"The original agent reply was not delivered because the trajectory may be unsafe.\n"
        f"Review the guardrail dashboard for diagnostic details."
    )
    blocked["payload"]["message"]["content"] = [{"type": "text", "text": block_text}]
    return blocked


async def _evaluate_async(trajectory: str, guardrail_url: str) -> dict[str, Any]:
    """Call guardrail service in thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _evaluate_sync, trajectory, guardrail_url
    )


def _evaluate_sync(trajectory: str, guardrail_url: str) -> dict[str, Any]:
    """Call guardrail service synchronously."""
    try:
        handler = urllib.request.ProxyHandler({})
        opener = urllib.request.build_opener(handler)
        body = json.dumps({"trajectory": trajectory, "tool_list": []}).encode("utf-8")
        req = urllib.request.Request(
            f"{guardrail_url}/evaluate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with opener.open(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        return {"prediction": -1, "label": "error", "reason": str(exc)}


def _read_gateway_token() -> str:
    """Read gateway auth token from OpenClaw config."""
    import os
    from pathlib import Path
    try:
        config_path = Path.home() / ".openclaw" / "openclaw.json"
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding="utf-8"))
            return data.get("gateway", {}).get("auth", {}).get("token", "")
    except Exception:
        pass
    return os.environ.get("OPENCLAW_GATEWAY_TOKEN", "")


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[GUARDRAIL-PROXY] {ts} {msg}", file=sys.stderr)
