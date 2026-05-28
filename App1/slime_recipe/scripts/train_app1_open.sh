#!/usr/bin/env bash
set -euo pipefail

COMMAND="${1:-run}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SESSION="${TMUX_SESSION:-train_gspo}"

usage() {
  cat >&2 <<'USAGE'
Usage:
  train_app1_open.sh run
  train_app1_open.sh stop

Required for run:
  QWEN35_RUN_DIR                 Output/run directory for this experiment.
  START_MODEL_DIR                HF checkpoint directory to initialize from.
  SLIME_ENV_SERVER_BASE_URL      Env server base URL, for example http://host:18080.
  SLIME_JUDGE_MODEL_URL          Judge OpenAI-compatible /v1 base URL.

Important optional envs:
  SLIME_RUN_MODE                 filter | nofilter | nofilter_malformedneg1. Default: filter.
  SLIME_ENV_SERVER_PARSER_ERROR_REWARD
                                  Parser-error reward. Auto-set to 0.0 for filter and -1.0 for nofilter_malformedneg1.
  APP1_OPEN_REINIT_SEED          Env server sampler reinit seed. Default: 20260521.
  APP1_OPEN_SHUFFLE_SEED         Local task/group shuffle seed. Default: 20260521.
  NUM_ROLLOUT                    Default: 800.
  ROLLOUT_BATCH_SIZE             Default: 32.
  GLOBAL_BATCH_SIZE              Default: rollout_batch_size * n_samples_per_prompt / num_steps_per_rollout.
  SAVE_INTERVAL                  Default: 50.
  KEEP_LAST_CHECKPOINTS          Default: 10.
  SLIME_SAVE_HF_ONLY             Default: 1.
  SLIME_ADVANTAGE_NORMALIZE_SCOPE
                                  Optional Slime-side advantage norm scope, e.g. task_type, if the runtime patch supports it.
USAGE
}

stop_training() {
  tmux kill-session -t "$SESSION" >/dev/null 2>&1 || true
  "$PYTHON_BIN" "$SCRIPT_DIR/ray_cli.py" stop --force >/dev/null 2>&1 || true
  pkill -f '/root/slime/train.py' >/dev/null 2>&1 || true
  pkill -f 'sglang' >/dev/null 2>&1 || true
  echo "stopped session=$SESSION ray/train/sglang on this worker"
}

export PATH=/usr/local/nvidia/bin:/usr/local/cuda/bin:/opt/conda/bin:/usr/bin:/usr/local/sbin:/usr/sbin:/sbin:/bin:$PATH
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/local/nvidia/lib64:/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}
export CUDNN_HOME=${CUDNN_HOME:-/usr/lib/x86_64-linux-gnu}
export SGLANG_DISABLE_CUDNN_CHECK=${SGLANG_DISABLE_CUDNN_CHECK:-1}
export CUDA_DEVICE_MAX_CONNECTIONS=${CUDA_DEVICE_MAX_CONNECTIONS:-1}
export NCCL_NVLS_ENABLE=${NCCL_NVLS_ENABLE:-0}

PYTHON_BIN="${PYTHON_BIN:-/usr/bin/python}"
SLIME_ROOT="${SLIME_ROOT:-/root/slime}"
MEGATRON_ROOT="${MEGATRON_ROOT:-/root/Megatron-LM}"

case "$COMMAND" in
  stop)
    stop_training
    exit 0
    ;;
  run)
    ;;
  -h|--help|help)
    usage
    exit 0
    ;;
  *)
    usage
    exit 2
    ;;
esac

: "${QWEN35_RUN_DIR:?set QWEN35_RUN_DIR}"
: "${START_MODEL_DIR:?set START_MODEL_DIR}"
: "${SLIME_ENV_SERVER_BASE_URL:?set SLIME_ENV_SERVER_BASE_URL}"
: "${SLIME_JUDGE_MODEL_URL:?set SLIME_JUDGE_MODEL_URL}"

export SLIME_ENV_SERVER_BASE_URL
export SLIME_ENV_SERVER_MAX_TURNS="${SLIME_ENV_SERVER_MAX_TURNS:-15}"
export SLIME_ENV_SERVER_LOG_SAMPLE_METRICS="${SLIME_ENV_SERVER_LOG_SAMPLE_METRICS:-0}"
export SLIME_JUDGE_MODEL_URL
export SLIME_JUDGE_MODEL_NAME="${SLIME_JUDGE_MODEL_NAME:-less_pair_p04_judge}"
export SLIME_JUDGE_ENABLE_THINKING="${SLIME_JUDGE_ENABLE_THINKING:-1}"
export SLIME_RUN_MODE="${SLIME_RUN_MODE:-filter}"
export WANDB_MODE="${WANDB_MODE:-offline}"
export WANDB_PROJECT="${WANDB_PROJECT:-app1-open-qwen35-4b}"
export WANDB_GROUP="${WANDB_GROUP:-app1-open-env-rl}"
export APP1_OPEN_REINIT_SEED="${APP1_OPEN_REINIT_SEED:-20260521}"
export APP1_OPEN_SHUFFLE_SEED="${APP1_OPEN_SHUFFLE_SEED:-20260521}"

RUN_DIR="$QWEN35_RUN_DIR"
mkdir -p "$RUN_DIR"
export WANDB_DIR="${WANDB_DIR:-$RUN_DIR/wandb}"
DATA_PATH="${DATA_PATH:-$RUN_DIR/train_tasks_clean_attacked_pure.jsonl}"
SAVE_DIR="${SAVE_DIR:-$RUN_DIR/qwen3_5_4b_train_checkpoints}"
MASTER_ADDR="${MASTER_ADDR:-127.0.0.1}"
KEEP_LAST_CHECKPOINTS="${KEEP_LAST_CHECKPOINTS:-10}"
ROLLOUT_BATCH_SIZE="${ROLLOUT_BATCH_SIZE:-32}"
N_SAMPLES_PER_PROMPT="${N_SAMPLES_PER_PROMPT:-8}"
NUM_STEPS_PER_ROLLOUT="${NUM_STEPS_PER_ROLLOUT:-1}"
GLOBAL_BATCH_SIZE="${GLOBAL_BATCH_SIZE:-$((ROLLOUT_BATCH_SIZE * N_SAMPLES_PER_PROMPT / NUM_STEPS_PER_ROLLOUT))}"
NUM_ROLLOUT="${NUM_ROLLOUT:-800}"
SAVE_INTERVAL="${SAVE_INTERVAL:-50}"
ADVANTAGE_ESTIMATOR="${ADVANTAGE_ESTIMATOR:-gspo}"
export KEEP_LAST_CHECKPOINTS
export SLIME_SAVE_HF_ONLY="${SLIME_SAVE_HF_ONLY:-1}"
export SLIME_SAVE_HF_DIR="${SLIME_SAVE_HF_DIR:-$RUN_DIR/hf_checkpoints/rollout_{rollout_id}}"
export PYTHONPATH="$MEGATRON_ROOT:$SLIME_ROOT:$SCRIPT_DIR:${PYTHONPATH:-}"

case "$SLIME_RUN_MODE" in
  filter)
    export SLIME_ENV_SERVER_PARSER_ERROR_REWARD="${SLIME_ENV_SERVER_PARSER_ERROR_REWARD:-0.0}"
    export SLIME_ROLLOUT_HOOK_MODE="${SLIME_ROLLOUT_HOOK_MODE:-filter}"
    ;;
  nofilter)
    unset SLIME_ENV_SERVER_PARSER_ERROR_REWARD
    export SLIME_ROLLOUT_HOOK_MODE="${SLIME_ROLLOUT_HOOK_MODE:-monitor_only}"
    ;;
  nofilter_malformedneg1)
    export SLIME_ENV_SERVER_PARSER_ERROR_REWARD="${SLIME_ENV_SERVER_PARSER_ERROR_REWARD:--1.0}"
    export SLIME_ROLLOUT_HOOK_MODE="${SLIME_ROLLOUT_HOOK_MODE:-monitor_only}"
    ;;
  *)
    echo "unknown SLIME_RUN_MODE=$SLIME_RUN_MODE" >&2
    exit 2
    ;;
esac

MODEL_ARGS=(
  --spec "slime_plugins.models.qwen3_5" "get_qwen3_5_spec"
  --disable-bias-linea
  --qk-layenorm
  --group-query-attention
  --num-attention-heads 16
  --num-query-groups 4
  --kv-channels 256
  --num-layers 32
  --hidden-size 2560
  --ffn-hidden-size 9216
  --use-gated-attention
  --normalization RMSNorm
  --apply-layenorm-1p
  --position-embedding-type rope
  --norm-epsilon 1e-6
  --rotary-percent 0.25
  --swiglu
  --vocab-size 248320
  --rotary-base 10000000
  --attention-output-gate
)

echo "=== app1_open Qwen3.5-4B Slime training ==="
echo "RUN_DIR=$RUN_DIR"
echo "START_MODEL_DIR=$START_MODEL_DIR"
echo "ENV_SERVER=$SLIME_ENV_SERVER_BASE_URL"
echo "JUDGE_URL=$SLIME_JUDGE_MODEL_URL"
echo "SLIME_RUN_MODE=$SLIME_RUN_MODE"
echo "SLIME_ROLLOUT_HOOK_MODE=$SLIME_ROLLOUT_HOOK_MODE"
echo "SLIME_ENV_SERVER_PARSER_ERROR_REWARD=${SLIME_ENV_SERVER_PARSER_ERROR_REWARD-<unset>}"
echo "APP1_OPEN_REINIT_SEED=$APP1_OPEN_REINIT_SEED"
echo "APP1_OPEN_SHUFFLE_SEED=$APP1_OPEN_SHUFFLE_SEED"
echo "NUM_ROLLOUT=$NUM_ROLLOUT ROLLOUT_BATCH_SIZE=$ROLLOUT_BATCH_SIZE GLOBAL_BATCH_SIZE=$GLOBAL_BATCH_SIZE SAVE_INTERVAL=$SAVE_INTERVAL KEEP_LAST_CHECKPOINTS=$KEEP_LAST_CHECKPOINTS"

"$PYTHON_BIN" - <<PY
import json
import urllib.request
url = "${SLIME_ENV_SERVER_BASE_URL}/admin/reinit-sampler"
payload = json.dumps({"seed": int("${APP1_OPEN_REINIT_SEED}"), "shuffle_seed": int("${APP1_OPEN_SHUFFLE_SEED}")}).encode()
req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=30) as response:
    print("REINIT", response.status, response.read().decode())
PY

"$PYTHON_BIN" - <<PY
import collections
import json
import math
import random
import re
import urllib.request
from pathlib import Path

base_url = "${SLIME_ENV_SERVER_BASE_URL}"
output_path = Path("${DATA_PATH}")
seed = int("${APP1_OPEN_SHUFFLE_SEED}")
with urllib.request.urlopen(f"{base_url}/health", timeout=30) as response:
    health = json.loads(response.read().decode())
print("ENV_HEALTH", health)
with urllib.request.urlopen(f"{base_url}/catalog/tasks", timeout=60) as response:
    payload = json.loads(response.read().decode())
tasks = payload["tasks"]

def normalize_task_id(task_id: str) -> str:
    task_id = str(task_id)
    task_id = re.sub(r"__query_malicious_\d+_[0-9a-f]+$", "", task_id)
    task_id = re.sub(r"__querytarget.*$", "", task_id, flags=re.IGNORECASE)
    task_id = re.sub(r"__tmpl_.*$", "", task_id)
    return task_id

def is_query_task(task: dict) -> bool:
    task_id = str(task.get("task_id", "")).lower()
    return "query_malicious" in task_id or "querytarget" in task_id

def is_attack_task(task: dict) -> bool:
    if is_query_task(task):
        return False
    task_id = str(task.get("task_id", "")).lower()
    scenarios = set(task.get("available_scenarios") or [])
    return "attacked" in scenarios and ("__tmpl_" in task_id or "attack" in task_id or "inject" in task_id)

def is_clean_task(task: dict) -> bool:
    return not is_query_task(task) and not is_attack_task(task)

def row_for(task: dict, scenario: str, category: str, family_key: str, group_position: str, pair_index):
    metadata = {
        "task_id": task["task_id"],
        "scenario": scenario,
        "score_family": "safety" if category == "attacked" else "clean",
        "score_mode": "per_scenario",
        "family_key": family_key,
        "group_position": group_position,
        "attack_pair_index": pair_index,
        "task_type": category,
        "harm_task_type": category,
        "safety_eval_family": category,
        "task_category": category,
        "has_grouped_attack_pair": True,
        "shuffle_unit": "attack_pair_group",
        "available_scenarios": task.get("available_scenarios") or [],
        "env_server_url": base_url,
        "domain": task.get("domain"),
        "difficulty_tier": task.get("difficulty_tier"),
        "selected_tools": task.get("selected_tools", []),
    }
    if category == "pure":
        metadata.update({
            "scenario": "clean",
            "task_type": "query_target",
            "harm_task_type": "query_target",
            "safety_eval_family": "query_target",
            "task_category": "pure",
            "is_malicious_query_task": True,
        })
    return {"prompt": [{"role": "user", "content": "task-placeholder"}], "metadata": metadata}

families = collections.defaultdict(lambda: {"clean": [], "attacked": [], "pure": []})
for task in tasks:
    family_key = normalize_task_id(task["task_id"])
    if is_query_task(task):
        families[family_key]["pure"].append(task)
    elif is_attack_task(task):
        families[family_key]["attacked"].append(task)
    elif is_clean_task(task):
        families[family_key]["clean"].append(task)

rng = random.Random(seed)
family_keys = list(families)
rng.shuffle(family_keys)
groups = []
counts = collections.Counter()
combo_counts = collections.Counter()
pair_count = 0
for family_key in family_keys:
    group = families[family_key]
    combo_counts[tuple(k for k in ("clean", "attacked", "pure") if group[k])] += 1
    clean = sorted(group["clean"], key=lambda x: x["task_id"])
    attacked = sorted(group["attacked"], key=lambda x: x["task_id"])
    pure = sorted(group["pure"], key=lambda x: x["task_id"])

    if attacked:
        for pair_index, attack_task in enumerate(attacked):
            unit = []
            if clean:
                unit.append(row_for(clean[0], "clean", "clean", family_key, "clean", pair_index)); counts["clean"] += 1
            unit.append(row_for(attack_task, "attacked", "attacked", family_key, "attack", pair_index)); counts["attacked"] += 1
            if pure:
                unit.append(row_for(pure[0], "clean", "pure", family_key, "query", pair_index)); counts["pure"] += 1
            groups.append(unit)
            pair_count += 1
    else:
        unit = []
        if clean:
            unit.append(row_for(clean[0], "clean", "clean", family_key, "clean", None)); counts["clean"] += 1
        if pure:
            unit.append(row_for(pure[0], "clean", "pure", family_key, "query", None)); counts["pure"] += 1
        if unit:
            groups.append(unit)

rng.shuffle(groups)
rows = [row for unit in groups for row in unit]
output_path.parent.mkdir(parents=True, exist_ok=True)
with output_path.open("w", encoding="utf-8", newline="\n") as handle:
    for row in rows:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
recommended = math.ceil(len(rows) / int("${ROLLOUT_BATCH_SIZE}"))
Path("${RUN_DIR}/recommended_num_rollout.txt").write_text(str(recommended), encoding="utf-8")
print(
    f"Wrote {len(rows)} shuffled attack-pair-group rows to {output_path}; "
    f"clean_rows={counts['clean']}; attacked_rows={counts['attacked']}; pure_rows={counts['pure']}; "
    f"families={len(family_keys)}; groups={len(groups)}; attack_pairs={pair_count}; "
    f"family_combos={dict(combo_counts)}; recommended_num_rollout={recommended}; configured_num_rollout=${NUM_ROLLOUT}"
)
PY

"$PYTHON_BIN" "$SCRIPT_DIR/ray_cli.py" stop --force >/dev/null 2>&1 || true
"$PYTHON_BIN" - <<'PY' || true
import os
import signal
import subprocess

current_pid = os.getpid()
output = subprocess.run(["ps", "-eo", "pid=,args="], check=False, stdout=subprocess.PIPE, text=True).stdout
for line in output.splitlines():
    stripped = line.strip()
    if not stripped:
        continue
    pid_text, _, args = stripped.partition(" ")
    try:
        pid = int(pid_text)
    except ValueError:
        continue
    if pid == current_pid or "sglang" not in args:
        continue
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
PY
sleep 2
"$PYTHON_BIN" "$SCRIPT_DIR/ray_cli.py" start --head --node-ip-address "$MASTER_ADDR" --num-gpus 4 --disable-usage-stats --dashboard-host=0.0.0.0 --dashboard-port=8265

checkpoint_pruner() {
  "$PYTHON_BIN" "$SCRIPT_DIR/best_ckpt_pruner.py"
}
checkpoint_pruner &
PRUNER_PID=$!
trap 'kill "$PRUNER_PID" >/dev/null 2>&1 || true' EXIT

HF_SAVE_ARGS=()
if [ "${SLIME_SAVE_HF_ONLY:-0}" = "1" ] || [ "${SLIME_SAVE_HF_ONLY:-false}" = "true" ]; then
  HF_SAVE_ARGS=(--save-hf "$SLIME_SAVE_HF_DIR" --save-hf-only)
fi

ROLLOUT_PROCESS_ARGS=()
case "${SLIME_ROLLOUT_HOOK_MODE:-filter}" in
  filter)
    ROLLOUT_PROCESS_ARGS=(--rollout-sample-filter-path rollout_malformed_filter.filter_malformed_tool_calls)
    ;;
  monitor_only)
    ROLLOUT_PROCESS_ARGS=(--rollout-all-samples-process-path rollout_malformed_filter.monitor_malformed_tool_calls_only)
    ;;
  none)
    ROLLOUT_PROCESS_ARGS=()
    ;;
  *)
    echo "unknown SLIME_ROLLOUT_HOOK_MODE=${SLIME_ROLLOUT_HOOK_MODE}" >&2
    exit 2
    ;;
esac

WANDB_KEY_ARGS=()
if [ -n "${WANDB_KEY:-}" ]; then
  WANDB_KEY_ARGS=(--wandb-key "$WANDB_KEY")
fi

ADV_NORM_ARGS=()
if [ -n "${SLIME_ADVANTAGE_NORMALIZE_SCOPE:-}" ]; then
  ADV_NORM_ARGS=(--advantage-normalize-scope "$SLIME_ADVANTAGE_NORMALIZE_SCOPE")
fi

COMMON_ARGS=(
  --hf-checkpoint "$START_MODEL_DIR"
  --ref-load "$START_MODEL_DIR"
  --prompt-data "$DATA_PATH"
  --input-key prompt
  --metadata-key metadata
  --apply-chat-template
  --custom-generate-function-path generate_with_env_server.generate
  "${ROLLOUT_PROCESS_ARGS[@]}"
  --rollout-max-prompt-len 2048
  --rollout-max-context-len 8192
  --rollout-max-response-len 1536
  --num-rollout "$NUM_ROLLOUT"
  --rollout-batch-size "$ROLLOUT_BATCH_SIZE"
  --n-samples-per-prompt "$N_SAMPLES_PER_PROMPT"
  --num-steps-per-rollout "$NUM_STEPS_PER_ROLLOUT"
  --rollout-temperature 0.5
  --global-batch-size "$GLOBAL_BATCH_SIZE"
  --advantage-estimator "$ADVANTAGE_ESTIMATOR"
  "${ADV_NORM_ARGS[@]}"
  --optimizer adam
  --lr 5e-7
  --lr-decay-style constant
  --weight-decay 0.0
  --adam-beta1 0.9
  --adam-beta2 0.95
  --save "$SAVE_DIR"
  --save-interval "$SAVE_INTERVAL"
  "${HF_SAVE_ARGS[@]}"
  --use-wandb
  --wandb-project "$WANDB_PROJECT"
  --wandb-group "$WANDB_GROUP"
  "${WANDB_KEY_ARGS[@]}"
  --tensor-model-parallel-size 4
  --pipeline-model-parallel-size 1
  --context-parallel-size 1
  --expert-model-parallel-size 1
  --expert-tensor-parallel-size 1
  --sequence-parallel
  --micro-batch-size 1
  --max-tokens-per-gpu 2048
  --qkv-format bshd
  --rollout-num-gpus-per-engine 4
  --sglang-mem-fraction-static 0.55
  --attention-dropout 0.0
  --hidden-dropout 0.0
  --attention-softmax-in-fp32
  --attention-backend flash
  --actor-num-nodes 1
  --actor-num-gpus-per-node 4
  --num-gpus-per-node 4
  --colocate
  --megatron-to-hf-mode bridge
  "${MODEL_ARGS[@]}"
)

echo "SAVE_DIR=$SAVE_DIR"
echo "WANDB_DIR=$WANDB_DIR"
echo "DATA_PATH=$DATA_PATH"
echo "ADVANTAGE_ESTIMATOR=$ADVANTAGE_ESTIMATOR"
echo "SLIME_ADVANTAGE_NORMALIZE_SCOPE=${SLIME_ADVANTAGE_NORMALIZE_SCOPE-<unset>}"
echo "parser_type=$(grep -m1 parser_type "$SCRIPT_DIR/generate_with_env_server.py" || true)"
"$PYTHON_BIN" "$SLIME_ROOT/train.py" "${COMMON_ARGS[@]}"
