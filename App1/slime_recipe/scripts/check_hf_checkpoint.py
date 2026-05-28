#!/usr/bin/env python3
import json
import sys
from pathlib import Path


WEIGHT_PATTERNS = (
    "model.safetensors",
    "model-*.safetensors",
    "pytorch_model*.bin",
    "adapter_model.safetensors",
)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_hf_checkpoint.py /path/to/hf_checkpoint", file=sys.stderr)
        return 2

    path = Path(sys.argv[1])
    if not path.is_dir():
        print(json.dumps({"ok": False, "error": "not a directory", "path": str(path)}, indent=2))
        return 1

    files = []
    for pattern in WEIGHT_PATTERNS:
        files.extend(path.glob(pattern))
    files = sorted(set(files))
    total_size = sum(p.stat().st_size for p in files)

    result = {
        "ok": bool(files) and total_size > 1024**3,
        "path": str(path),
        "weight_file_count": len(files),
        "weight_size_gib": round(total_size / 1024**3, 3),
        "weight_files": [p.name for p in files],
        "has_index": (path / "model.safetensors.index.json").exists(),
        "metadata_files": sorted(p.name for p in path.glob("*.json")),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
