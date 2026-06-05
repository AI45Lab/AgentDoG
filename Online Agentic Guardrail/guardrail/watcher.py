"""Session file watcher — polls JSONL files for new events."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_OPENCLAW_SESSIONS_GLOB = "~/.openclaw/agents/*/sessions"
_SESSION_DIR_ENV_KEYS = (
    "GUARDRAIL_SESSIONS_DIRS",
    "OPENCLAW_SESSIONS_DIRS",
    "OPENCLAW_SESSIONS_DIR",
)


def resolve_sessions_dir_arg(sessions_dir: str = "") -> str:
    """Return explicit session dirs or the default OpenClaw all-agent glob."""
    value = sessions_dir.strip()
    if value:
        return value
    for key in _SESSION_DIR_ENV_KEYS:
        env_value = os.environ.get(key, "").strip()
        if env_value:
            return env_value
    return DEFAULT_OPENCLAW_SESSIONS_GLOB


class SessionWatcher:
    """Poll a JSONL file for new lines using byte-offset tracking."""

    def __init__(self, filepath: str) -> None:
        self.filepath = filepath
        self._offset = 0

    def poll(self) -> list[dict[str, Any]]:
        """Read new lines since last poll. Returns parsed message events."""
        try:
            size = os.path.getsize(self.filepath)
        except OSError:
            return []
        if size <= self._offset:
            return []

        events: list[dict[str, Any]] = []
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                f.seek(self._offset)
                new_data = f.read()
                self._offset = f.tell()
        except OSError:
            return []

        for line in new_data.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                event = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
        return events

    def get_all(self) -> list[dict[str, Any]]:
        """Read all events from the start."""
        self._offset = 0
        return self.poll()


class SessionDiscovery:
    """Find available session JSONL files across multiple agent directories.

    Accepts a single directory, a glob pattern (containing *), or a
    comma-separated list of directories.
    """

    def __init__(self, sessions_dir: str) -> None:
        self.dirs: list[Path] = []
        if not sessions_dir:
            return
        import glob as _glob
        for part in sessions_dir.split(","):
            part = part.strip()
            if not part:
                continue
            part = os.path.expandvars(os.path.expanduser(part))
            if "*" in part:
                self.dirs.extend(Path(p) for p in _glob.glob(part) if Path(p).is_dir())
            else:
                p = Path(part)
                if p.is_dir():
                    self.dirs.append(p)

    @property
    def all_dirs(self) -> list[str]:
        return [str(d) for d in self.dirs]

    def list_sessions(self) -> list[dict[str, Any]]:
        """Return session files sorted by modification time (newest first)."""
        sessions: list[dict[str, Any]] = []
        for directory in self.dirs:
            agent_id = self._derive_agent_id(directory)
            for path in directory.glob("*.jsonl"):
                if "." in path.stem:
                    continue
                try:
                    stat = path.stat()
                    meta = self._extract_metadata(path)
                    sessions.append({
                        "path": str(path),
                        "name": path.stem,
                        "mtime": stat.st_mtime,
                        "size": stat.st_size,
                        "agent_id": agent_id,
                        **meta,
                    })
                except OSError:
                    continue
        sessions.sort(key=lambda s: s["mtime"], reverse=True)
        return sessions

    @staticmethod
    def _derive_agent_id(sessions_dir: Path) -> str:
        if sessions_dir.name == "sessions":
            return sessions_dir.parent.name
        return sessions_dir.name

    @staticmethod
    def _extract_metadata(path: Path) -> dict[str, Any]:
        """Read session file to get model, channel, event/tool counts, and title."""
        meta: dict[str, Any] = {
            "model": "", "channel": "unknown",
            "event_count": 0, "tool_calls": 0, "title": "",
        }
        try:
            msg_count = 0
            tc_count = 0
            first_user_text = ""
            with open(path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if ev.get("type") == "message":
                        msg_count += 1
                        msg = ev.get("message", {})
                        role = msg.get("role", "")
                        content = msg.get("content", [])

                        if role == "user" and not first_user_text:
                            text = ""
                            if isinstance(content, str):
                                text = content
                            elif isinstance(content, list):
                                for c in content:
                                    if isinstance(c, dict) and c.get("text"):
                                        text = c["text"]
                                        break
                            clean = text.strip()
                            if "Conversation info" in clean or "sender_id" in clean:
                                meta["channel"] = "telegram"
                                # User message is after all ``` blocks
                                parts = clean.split("```")
                                tail = parts[-1].strip() if len(parts) > 1 else ""
                                if tail:
                                    first_user_text = tail.split("\n")[0][:60]
                            elif clean:
                                snippet = clean.split("\n")[0][:60]
                                if snippet.startswith("Read HEARTBEAT"):
                                    first_user_text = "Cron Heartbeat"
                                elif snippet.startswith("[cron:"):
                                    first_user_text = "Cron Task"
                                else:
                                    first_user_text = snippet

                        if role == "assistant" and isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "toolCall":
                                    tc_count += 1

                    elif ev.get("type") == "model_change" and not meta.get("model"):
                        meta["model"] = ev.get("modelId", "")
                    if i > 500:
                        break
            meta["event_count"] = msg_count
            meta["tool_calls"] = tc_count
            meta["title"] = first_user_text or ""
        except OSError:
            pass
        return meta
