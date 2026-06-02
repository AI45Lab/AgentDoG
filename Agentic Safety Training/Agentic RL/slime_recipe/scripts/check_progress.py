#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_progress.py /path/to/train.log", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    text = path.read_text(errors="replace")

    rollouts = [int(x) for x in re.findall(r"rollout (\d+)", text)]
    steps = [int(x) for x in re.findall(r"model\.py:\d+ - step (\d+):", text)]
    raw_rewards = [float(x) for x in re.findall(r"'rollout/raw_reward': ([0-9.eE+-]+)", text)]
    monitor_lines = [line for line in text.splitlines() if "rollout_monitor=" in line]

    result = {
        "log": str(path),
        "latest_rollout": max(rollouts) if rollouts else None,
        "latest_train_step": max(steps) if steps else None,
        "latest_raw_reward": raw_rewards[-1] if raw_rewards else None,
        "monitor_count": len(monitor_lines),
    }

    if monitor_lines:
        last = monitor_lines[-1]
        match = re.search(r"rollout_monitor=(\{.*\})", last)
        if match:
            try:
                result["latest_monitor"] = json.loads(match.group(1))
            except Exception:
                result["latest_monitor_parse_error"] = True

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
