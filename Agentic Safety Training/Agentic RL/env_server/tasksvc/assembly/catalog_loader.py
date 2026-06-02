import json
import os
import tempfile
from pathlib import Path

from tasksvc.assembly.bundle_validator import validate_runtime_bundle, validate_task_draft


def _read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _is_runtime_bundle(value):
    return isinstance(value, dict) and "task_spec" in value and "execution_bundle" in value


def _is_task_draft(value):
    return isinstance(value, dict) and "planned_task" in value and "state_draft" in value


def normalize_runtime_catalog_payload(payload):
    if isinstance(payload, dict) and "runtime_catalog" in payload:
        payload = payload["runtime_catalog"]
    elif isinstance(payload, dict) and "task_drafts" in payload:
        payload = payload["task_drafts"]
    elif isinstance(payload, dict) and "bundle" in payload:
        payload = payload["bundle"]
    elif isinstance(payload, dict) and "task_draft" in payload:
        payload = payload["task_draft"]

    if _is_runtime_bundle(payload):
        validate_runtime_bundle(payload)
        return {payload["task_spec"]["task_id"]: payload}

    if _is_task_draft(payload):
        raise ValueError("This runtime release only loads prebuilt runtime bundles. Convert task_draft payloads before serving.")

    if isinstance(payload, list):
        raise ValueError("This runtime release only loads prebuilt runtime catalogs, not task_drafts lists.")

    if isinstance(payload, dict):
        if payload and all(_is_runtime_bundle(value) for value in payload.values()):
            for bundle in payload.values():
                validate_runtime_bundle(bundle)
            return payload
        if payload and all(_is_task_draft(value) for value in payload.values()):
            raise ValueError("This runtime release only loads prebuilt runtime catalogs, not task_drafts dicts.")

    raise ValueError(
        "Catalog payload must contain a runtime_catalog dict, a task_drafts list/dict, a single bundle, or a single task_draft."
    )


def load_runtime_catalog_from_file(path):
    payload = _read_json(path)
    return normalize_runtime_catalog_payload(payload)


def export_json(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
