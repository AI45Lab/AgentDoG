#!/usr/bin/env bash
set -euo pipefail

export PATH=/usr/local/nvidia/bin:/usr/local/cuda/bin:/opt/conda/bin:/usr/bin:/bin:$PATH
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/local/nvidia/lib64:/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}
export CUDNN_HOME=/usr/lib/x86_64-linux-gnu
export SGLANG_DISABLE_CUDNN_CHECK=1

: "${JUDGE_MODEL_PATH:?set JUDGE_MODEL_PATH}"
MODEL_PATH="$JUDGE_MODEL_PATH"
MODEL_NAME="${JUDGE_MODEL_NAME:-less_pair_p04_judge}"
HOST="${JUDGE_HOST:-0.0.0.0}"
PORT="${JUDGE_PORT:-18081}"
CONTEXT_LENGTH="${JUDGE_CONTEXT_LENGTH:-32768}"
MEM_FRACTION="${JUDGE_MEM_FRACTION_STATIC:-0.82}"

exec python -m sglang.launch_server \
  --model-path "$MODEL_PATH" \
  --served-model-name "$MODEL_NAME" \
  --host "$HOST" \
  --port "$PORT" \
  --trust-remote-code \
  --context-length "$CONTEXT_LENGTH" \
  --mem-fraction-static "$MEM_FRACTION"
