"""Guardrail HTTP microservice with real-time monitoring dashboard.

Endpoints:
    GET  /                    → Dashboard UI
    GET  /health              → {"status": "ok"}
    GET  /dashboard/sessions  → list available session files
    GET  /dashboard/events    → SSE stream for real-time monitoring
    GET  /evaluate/cache      → return cached evaluation for a session (by file size)
    POST /evaluate            → accepts trajectory text + tool list, returns verdict
    POST /check               → accepts raw session_events JSONL, returns verdict
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections import deque
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs

from guardrail.config import GuardrailConfig
from guardrail.evaluator import evaluate
from guardrail.trajectory import extract_tool_list, extract_trajectory_text
from guardrail.watcher import SessionWatcher, SessionDiscovery, resolve_sessions_dir_arg


_DASHBOARD_ASSETS = {
    "/inspections.html": "text/html; charset=utf-8",
    "/assets/agentdog-logo.png": "image/png",
    "/assets/agentdog-mark.png": "image/png",
}


def _resolve_dashboard_asset(path: str) -> Path | None:
    """Resolve explicitly allowed dashboard companion pages."""
    if path not in _DASHBOARD_ASSETS:
        return None
    return Path(__file__).parent / path.lstrip("/")


# Shared event bus: plugin calls /evaluate → result pushed here → SSE picks it up
_live_events: deque[dict[str, Any]] = deque(maxlen=200)
_live_events_lock = threading.Lock()
_live_event_counter = 0


def _push_live_event(event: dict[str, Any]) -> None:
    global _live_event_counter
    with _live_events_lock:
        _live_event_counter += 1
        event["_seq"] = _live_event_counter
        event["_ts"] = time.time()
        _live_events.append(event)


def _get_live_events_since(seq: int) -> list[dict[str, Any]]:
    with _live_events_lock:
        return [e for e in _live_events if e.get("_seq", 0) > seq]


def _cache_path(session_path: str) -> Path:
    return Path(session_path + ".guardrail.json")


def _read_eval_cache(session_path: str) -> dict[str, Any] | None:
    cp = _cache_path(session_path)
    if not cp.exists():
        return None
    try:
        data = json.loads(cp.read_text(encoding="utf-8"))
        current_size = os.path.getsize(session_path)
        if data.get("_file_size") != current_size:
            return None
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _write_eval_cache(session_path: str, result: dict[str, Any]) -> None:
    try:
        current_size = os.path.getsize(session_path)
    except OSError:
        return
    cache_data = {**result, "_file_size": current_size}
    try:
        _cache_path(session_path).write_text(
            json.dumps(cache_data, ensure_ascii=False), encoding="utf-8",
        )
    except OSError:
        pass
    _append_eval_history(session_path, result)


def _history_path(session_path: str) -> Path:
    return Path(session_path + ".guardrail-history.jsonl")


def _append_eval_history(session_path: str, result: dict[str, Any]) -> None:
    entry = {**result, "_ts": time.time()}
    try:
        with open(_history_path(session_path), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _read_eval_history(session_path: str) -> list[dict[str, Any]]:
    hp = _history_path(session_path)
    if not hp.exists():
        return []
    results = []
    try:
        for line in hp.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    return results


class GuardrailHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the guardrail service."""

    config: GuardrailConfig
    sessions_dir: str = ""
    sessions_dirs_resolved: list[str] = []

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "":
            self._serve_dashboard()
        elif path == "/health":
            self._json_response(200, {"status": "ok", "model": self.config.model})
        elif path == "/dashboard/sessions":
            self._handle_list_sessions()
        elif path == "/dashboard/events":
            self._handle_sse(parsed)
        elif path == "/evaluate/cache":
            self._handle_eval_cache(parsed)
        else:
            asset_path = _resolve_dashboard_asset(path)
            if asset_path is not None:
                self._serve_asset(asset_path, _DASHBOARD_ASSETS[path])
            else:
                self._json_response(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path == "/evaluate":
            self._handle_evaluate()
        elif self.path == "/check":
            self._handle_check()
        else:
            self._json_response(404, {"error": "not found"})

    # --- Dashboard ---

    def _serve_dashboard(self) -> None:
        html_path = Path(__file__).parent / "dashboard.html"
        self._serve_asset(html_path, "text/html; charset=utf-8")

    def _serve_asset(self, path: Path, content_type: str) -> None:
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            self._json_response(404, {"error": f"{path.name} not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _handle_list_sessions(self) -> None:
        if not self.sessions_dir:
            self._json_response(200, [])
            return
        discovery = SessionDiscovery(self.sessions_dir)
        sessions = discovery.list_sessions()
        for s in sessions:
            cached = _read_eval_cache(s["path"])
            if cached:
                s["verdict"] = _prediction_label(cached.get("prediction", -1))
                s["verdict_reason"] = cached.get("reason", "")
                s["verdict_model"] = cached.get("model", "")
                s["verdict_prediction"] = cached.get("prediction", -1)
            else:
                s["verdict"] = None
            history = _read_eval_history(s["path"])
            s["eval_history"] = [
                {
                    "prediction": h.get("prediction", -1),
                    "label": _prediction_label(h.get("prediction", -1)),
                    "reason": h.get("reason", ""),
                    "model": h.get("model", ""),
                    "ts": h.get("_ts", 0),
                }
                for h in history
            ]
        self._json_response(200, sessions)

    def _handle_sse(self, parsed) -> None:
        params = parse_qs(parsed.query)
        session_path = params.get("session", [""])[0]

        # If no session specified, just stream live evaluation events
        stream_mode = "live" if not session_path else "session"

        if stream_mode == "session":
            if self.sessions_dirs_resolved:
                real_session = os.path.realpath(session_path)
                allowed = any(
                    real_session.startswith(os.path.realpath(d))
                    for d in self.sessions_dirs_resolved
                )
                if not allowed:
                    self._json_response(403, {"error": "path not allowed"})
                    return
            if not os.path.exists(session_path):
                self._json_response(404, {"error": f"session file not found: {session_path}"})
                return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        if stream_mode == "session":
            self._stream_session(session_path)
        else:
            self._stream_live()

    def _stream_session(self, session_path: str) -> None:
        """Stream session file events + live evaluation results."""
        watcher = SessionWatcher(session_path)
        last_live_seq = _live_event_counter

        try:
            initial_events = watcher.get_all()
            self._sse_send("init", initial_events)

            while True:
                # Poll file for new session events
                new_events = watcher.poll()
                for event in new_events:
                    self._sse_send("message", event)

                # Check for live evaluation results from plugin calls
                live_events = _get_live_events_since(last_live_seq)
                for le in live_events:
                    last_live_seq = le.get("_seq", last_live_seq)
                    etype = le.get("_type", "evaluation")
                    self._sse_send(etype, {
                        k: v for k, v in le.items() if not k.startswith("_")
                    })

                time.sleep(0.3)

        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _stream_live(self) -> None:
        """Stream only live evaluation events (no session file)."""
        last_live_seq = _live_event_counter
        try:
            while True:
                live_events = _get_live_events_since(last_live_seq)
                for le in live_events:
                    last_live_seq = le.get("_seq", last_live_seq)
                    etype = le.get("_type", "evaluation")
                    self._sse_send(etype, {
                        k: v for k, v in le.items() if not k.startswith("_")
                    })
                time.sleep(0.3)
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _sse_send(self, event_type: str, data: Any) -> None:
        payload = json.dumps(data, ensure_ascii=False)
        message = f"event: {event_type}\ndata: {payload}\n\n"
        self.wfile.write(message.encode("utf-8"))
        self.wfile.flush()

    # --- Evaluation cache ---

    def _handle_eval_cache(self, parsed) -> None:
        params = parse_qs(parsed.query)
        session_path = params.get("session", [""])[0]
        if not session_path:
            self._json_response(400, {"error": "missing session param"})
            return
        cached = _read_eval_cache(session_path)
        if cached:
            result = {k: v for k, v in cached.items() if not k.startswith("_")}
            self._json_response(200, {"cached": True, **result})
        else:
            self._json_response(200, {"cached": False})

    # --- API endpoints ---

    def _handle_evaluate(self) -> None:
        body = self._read_body()
        if body is None:
            return
        trajectory = body.get("trajectory", "")
        tool_list = body.get("tool_list", [])
        session_path = body.get("session_path", "")
        if not trajectory:
            self._json_response(200, {
                "prediction": 0, "label": "safe",
                "reason": "Empty trajectory", "model": self.config.model,
            })
            return

        # Push trajectory to live event bus so Dashboard sees it immediately
        _push_live_event({
            "_type": "trajectory",
            "trajectory": trajectory[:2000],
            "tool_list": tool_list,
        })

        result = _evaluate_trajectory(trajectory, tool_list, self.config)

        if session_path and result.get("prediction") != -1:
            _write_eval_cache(session_path, result)

        # Push evaluation result to live event bus
        _push_live_event({
            "_type": "evaluation",
            **result,
        })

        self._json_response(200, result)

    def _handle_check(self) -> None:
        body = self._read_body()
        if body is None:
            return
        session_events_text = body.get("session_events", "")
        if not session_events_text:
            self._json_response(200, {
                "prediction": 0, "label": "safe",
                "reason": "No session events", "model": self.config.model,
            })
            return

        result = evaluate(session_events_text, self.config)
        eval_result = {
            "prediction": result.prediction,
            "label": _prediction_label(result.prediction),
            "reason": result.reason,
            "model": result.model,
            "error": result.error,
        }

        _push_live_event({"_type": "evaluation", **eval_result})

        self._json_response(200, eval_result)

    def _read_body(self) -> dict[str, Any] | None:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._json_response(400, {"error": "empty request body"})
            return None
        try:
            raw = self.rfile.read(content_length)
            return json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            self._json_response(400, {"error": f"invalid JSON: {exc}"})
            return None

    def _json_response(self, status: int, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        sys.stderr.write(f"[GUARDRAIL] {timestamp} {format % args}\n")


def _evaluate_trajectory(
    trajectory: str, tool_list: list[str], config: GuardrailConfig,
) -> dict[str, Any]:
    from guardrail.prompt import AGENTDOG_TRAJ_PROMPT
    from guardrail.evaluator import _call_api, _extract_content, _parse_response

    tool_list_text = ", ".join(tool_list) if tool_list else "(none)"
    prompt = AGENTDOG_TRAJ_PROMPT.format(
        trajectory=trajectory, tool_list_text=tool_list_text,
    )
    try:
        raw_response = _call_api(prompt, config)
        content = _extract_content(raw_response)
        pred, reason = _parse_response(content)
    except Exception as exc:
        return {
            "prediction": -1, "label": "error",
            "reason": f"Evaluation failed: {exc}",
            "model": config.model, "error": str(exc),
        }
    return {
        "prediction": pred, "label": _prediction_label(pred),
        "reason": reason, "model": config.model, "error": None,
    }


def _prediction_label(prediction: int) -> str:
    if prediction == 0:
        return "safe"
    if prediction == 1:
        return "unsafe"
    return "error"


def serve(
    config: GuardrailConfig,
    host: str = "0.0.0.0",
    port: int = 8340,
    sessions_dir: str = "",
) -> None:
    """Start the guardrail HTTP service with dashboard."""
    sessions_dir = resolve_sessions_dir_arg(sessions_dir)
    GuardrailHandler.config = config
    GuardrailHandler.sessions_dir = sessions_dir
    discovery = SessionDiscovery(sessions_dir)
    GuardrailHandler.sessions_dirs_resolved = discovery.all_dirs
    server = ThreadingHTTPServer((host, port), GuardrailHandler)
    print(f"[GUARDRAIL] Service listening on http://{host}:{port}", file=sys.stderr)
    print(f"[GUARDRAIL] Model: {config.model}", file=sys.stderr)
    print(f"[GUARDRAIL] Dashboard: http://{host}:{port}/", file=sys.stderr)
    if sessions_dir:
        print(f"[GUARDRAIL] Sessions dir: {sessions_dir}", file=sys.stderr)
        for d in discovery.all_dirs:
            print(f"[GUARDRAIL]   resolved: {d}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[GUARDRAIL] Shutting down", file=sys.stderr)
        server.shutdown()
