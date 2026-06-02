# Qwen3.5 Safety Env RL Slime Recipe

This recipe packages the current Slime env-RL setup into reusable config and scripts.

## Reward

```text
clean benign:   R = U
pure malicious: R = S
attacked benign: R = 0.5 * U + 0.25 * S + 0.25 * U * S
```

`U` is the env utility reward. `S` is the judge safety score, with `safe=1` and `unsafe=0`.

The reward is computed in `scripts/generate_with_env_server.py` and attached to `sample.reward`.
Pure malicious samples are rewritten to `R=S` in `scripts/rollout_malformed_filter.py`.

## Files

```text
recipe.yaml                         experiment matrix and default settings
scripts/generate_with_env_server.py reward/env/judge rollout harness
scripts/rollout_malformed_filter.py loss filter, monitor, pure reward rewrite
scripts/train_app1_open.sh          unified Slime training entrypoint
scripts/run_slime_train.sh          compatibility wrapper to train_app1_open.sh run
scripts/qwen3.5-4B.sh               compatibility note; model args are in train_app1_open.sh
scripts/start_train_from_recipe.sh  compatibility wrapper to train_app1_open.sh run
scripts/start_judge.sh              judge server launcher
scripts/stop_train.sh               compatibility wrapper to train_app1_open.sh stop
scripts/ray_cli.py                  Ray CLI shim
scripts/best_ckpt_pruner.py         checkpoint retention helper
scripts/check_progress.py           parse train.log status
scripts/check_hf_checkpoint.py      validate saved HF checkpoint has weights
slime_patches/README.md             required Slime runtime patch behavior
```

## Required Runtime

Run on a PJLab worker with the qwen35 Slime image and these mounts:

```bash
--mount=gpfs://gpfs1/chenguanxu:/mnt/shared-storage-user/chenguanxu
--mount=gpfs://gpfs1/ai4good1-share:/mnt/shared-storage-user/ai4good1-share
--mount=gpfs://gpfs2/gpfs2-shared-public:/mnt/shared-storage-gpfs2/gpfs2-shared-public
--mount=gpfs://gpfs2/ai4good1-share-gpfs2:/mnt/shared-storage-gpfs2/ai4good1-share-gpfs2
```

Runtime exports:

```bash
export PATH=/usr/local/nvidia/bin:/usr/local/cuda/bin:/opt/conda/bin:/usr/bin:/bin:$PATH
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:/usr/local/nvidia/lib64:/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}
export CUDNN_HOME=/usr/lib/x86_64-linux-gnu
```

## Start A Judge

```bash
bash scripts/start_judge.sh
```

`JUDGE_MODEL_PATH` is required. It serves `less_pair_p04_judge` on port `18081` by default.

## Start One Training Run

Example:

```bash
export RUN_NAME=ckpt_noadv_nofilter_malformedneg1
export QWEN35_RUN_DIR=/path/to/output/$RUN_NAME
export START_MODEL_DIR=/path/to/start/model-or-checkpoint
export SLIME_ENV_SERVER_BASE_URL=http://env-server-host:18080
export SLIME_JUDGE_MODEL_URL=http://judge-host:18081
export SLIME_RUN_MODE=nofilter_malformedneg1
bash scripts/train_app1_open.sh run
```

The wrapper performs:

```text
POST /admin/reinit-sampler {"seed": 20260521, "shuffle_seed": 20260521}
```

before launching Slime.

## Run Modes

```text
filter:
  malformed/tool-call broken samples are removed from loss
  parser error reward = 0.0

nofilter:
  samples are not removed
  monitor metrics are still recorded
  pure malicious reward is still rewritten to S

nofilter_malformedneg1:
  samples are not removed
  malformed parser reward = -1.0
  pure malicious reward is still rewritten to S
```

## Check Progress

```bash
python scripts/check_progress.py /path/to/train.log
```

## Check HF Checkpoint

```bash
python scripts/check_hf_checkpoint.py /path/to/hf_checkpoints/rollout_49
```

This fails if the directory only has tokenizer/config metadata and no model weights.

## Current Six-Run Matrix

See `recipe.yaml -> current_six_run_matrix`.

All six use:

```text
advantage_estimator=gspo
task advnorm=off
rollout_batch_size=32
n_samples_per_prompt=8
global_batch_size=256
num_rollout=800
save_interval=50
save_hf_only=true
keep_last_checkpoints=10
seed=20260521
shuffle_seed=20260521
```

## Important Checkpoint Note

Do not accept a 20MB `hf_checkpoints/rollout_*` directory as a real HF checkpoint.
A valid full HF checkpoint must contain at least one of:

```text
model.safetensors
model-*.safetensors
pytorch_model*.bin
adapter_model.safetensors
```

For this full-model setup, expected size is GiB-level, not MB-level.

On a fresh worker, apply or verify the Slime runtime patch described in
`slime_patches/README.md` before enabling `SLIME_SAVE_HF_ONLY=1`.
