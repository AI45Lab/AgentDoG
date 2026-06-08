from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_GUARDRAIL_MODEL = "agentdog"


@dataclass(frozen=True)
class GuardrailConfig:
    enabled: bool = False
    api_base: str = ""
    model: str = DEFAULT_GUARDRAIL_MODEL
    api_key: str = ""
    timeout_seconds: int = 60


def load_config(path: str | Path) -> GuardrailConfig:
    """Load guardrail config from a JSON file."""
    text = Path(path).read_text(encoding="utf-8")
    raw = json.loads(text)
    if not isinstance(raw, dict):
        raise ValueError(f"Guardrail config must be a JSON object: {path}")
    return load_config_from_dict(raw)


def load_config_from_dict(raw: dict[str, Any]) -> GuardrailConfig:
    """Build GuardrailConfig from a dict. String fields support $ENV_VAR syntax."""

    return GuardrailConfig(
        enabled=_get_bool(raw, "enabled", default=False),
        api_base=_get_str(raw, "api_base", default=""),
        model=_get_str(raw, "model", default=DEFAULT_GUARDRAIL_MODEL),
        api_key=_get_str(raw, "api_key", default=""),
        timeout_seconds=_get_int(raw, "timeout_seconds", default=60),
    )


def _get_bool(data: dict[str, Any], key: str, *, default: bool) -> bool:
    value = data.get(key, default)
    if isinstance(value, bool):
        return value
    return default


def _get_str(data: dict[str, Any], key: str, *, default: str) -> str:
    value = data.get(key, default)
    if isinstance(value, str):
        if value.startswith("$"):
            env_value = os.environ.get(value[1:], "")
            return env_value if env_value else default
        return value
    return default


def _get_int(data: dict[str, Any], key: str, *, default: int) -> int:
    value = data.get(key, default)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return default
