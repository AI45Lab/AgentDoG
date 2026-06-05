"""PRE_REPLY Guardrail — framework-agnostic trajectory safety evaluator.

Can be used as:
  - HTTP service:  python -m guardrail serve --port 8340
  - CLI tool:      python -m guardrail check path/to/session_events.jsonl
  - Python library: from guardrail import evaluate, load_config
"""

from guardrail.config import GuardrailConfig, load_config, load_config_from_dict
from guardrail.evaluator import GuardrailResult, evaluate
from guardrail.runner import run_guardrail_check, scan_artifacts_dir
from guardrail.server import serve
from guardrail.trajectory import extract_tool_list, extract_trajectory_text

__all__ = [
    "GuardrailConfig",
    "GuardrailResult",
    "evaluate",
    "extract_tool_list",
    "extract_trajectory_text",
    "load_config",
    "load_config_from_dict",
    "run_guardrail_check",
    "scan_artifacts_dir",
    "serve",
]
