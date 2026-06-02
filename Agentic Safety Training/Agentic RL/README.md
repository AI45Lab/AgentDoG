# Agentic RL Open Release

This folder combines the open-source environment server release and the Slime training recipe used for APP1/Qwen3.5 safety RL.

Environment data is available at [quantumfr/agentic-lightweight-envs-runtime-20260528](https://huggingface.co/datasets/quantumfr/agentic-lightweight-envs-runtime-20260528), covering lightweight runtime environments for scalable agentic safety RL experiments.

## Layout

- env_server/: Open-source runtime environment server, task data, docs, smoke/stress tools.
- slime_recipe/: Slime GSPO recipe, reward harness, rollout hooks, judge/train helpers.

## Main Training Reward

- clean benign: R = U
- pure malicious: R = S
- attacked benign: R = 0.5 * U + 0.25 * S + 0.25 * U * S

U is utility from the env server. S is judge safety, safe=1 and unsafe=0.

## Typical Flow

1. Start an env server from env_server/.
2. Start a judge server with slime_recipe/scripts/start_judge.sh.
3. Start Slime training with slime_recipe/scripts/start_train_from_recipe.sh.
4. Check progress with slime_recipe/scripts/check_progress.py.
5. Validate HF checkpoints with slime_recipe/scripts/check_hf_checkpoint.py.

See env_server/README.md and slime_recipe/README.md for details.
