#!/usr/bin/env bash
set -euo pipefail

RUN_DIR="${1:?run dir required}"
BASE_URL="${2:?base url required}"
SERVER_PID="${3:?server pid required}"
EPISODES_PER_LEVEL="${4:-256}"
shift 4 || true
LEVELS=("$@")
if [ ${#LEVELS[@]} -eq 0 ]; then
  LEVELS=(64 128 192 256)
fi

export PATH=/usr/local/nvidia/bin:/opt/conda/bin:/usr/bin:/bin:$PATH
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

mkdir -p "$RUN_DIR"
REPORT="$RUN_DIR/stress_report.json"
MONITOR="$RUN_DIR/server_resource_monitor.jsonl"
STDOUT_LOG="$RUN_DIR/stress_stdout.log"
STDERR_LOG="$RUN_DIR/stress_stderr.log"

cd "$REPO_ROOT"

python3 scripts/env_server_stress_test.py \
  --base-url "$BASE_URL" \
  --concurrency "${LEVELS[@]}" \
  --episodes-per-level "$EPISODES_PER_LEVEL" \
  --output "$REPORT" \
  >"$STDOUT_LOG" 2>"$STDERR_LOG" &
STRESS_PID=$!
echo "$STRESS_PID" > "$RUN_DIR/stress.pid"

while kill -0 "$STRESS_PID" 2>/dev/null; do
  ts=$(date -Is)
  ps_line=$(ps -p "$SERVER_PID" -o pid=,%cpu=,%mem=,rss=,vsz=,etime= 2>/dev/null | awk '{print $1" "$2" "$3" "$4" "$5" "$6}')
  free_line=$(free -m | awk 'NR==2 {print $2" "$3" "$4" "$7}')
  python3 - <<PY >> "$MONITOR"
import json
ps_line = """$ps_line""".strip().split()
free_line = """$free_line""".strip().split()
payload = {
  "timestamp": "$ts",
  "server_pid": int(ps_line[0]) if len(ps_line) >= 1 else None,
  "cpu_percent": float(ps_line[1]) if len(ps_line) >= 2 else None,
  "mem_percent": float(ps_line[2]) if len(ps_line) >= 3 else None,
  "rss_kb": int(ps_line[3]) if len(ps_line) >= 4 else None,
  "vsz_kb": int(ps_line[4]) if len(ps_line) >= 5 else None,
  "etime": ps_line[5] if len(ps_line) >= 6 else None,
  "mem_total_mb": int(free_line[0]) if len(free_line) >= 1 else None,
  "mem_used_mb": int(free_line[1]) if len(free_line) >= 2 else None,
  "mem_free_mb": int(free_line[2]) if len(free_line) >= 3 else None,
  "mem_available_mb": int(free_line[3]) if len(free_line) >= 4 else None,
}
print(json.dumps(payload, ensure_ascii=False))
PY
  sleep 5
done

wait "$STRESS_PID"
