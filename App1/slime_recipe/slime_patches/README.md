# Slime Runtime Patch Requirements

This recipe assumes the Slime runtime supports:

```text
--save-hf
--save-hf-only
```

and that HF export is validated as a real model checkpoint, not only tokenizer/config metadata.

The active workers used for this experiment were patched in:

```text
/root/slime/slime/utils/arguments.py
/root/slime/slime/backends/megatron_utils/actor.py
/root/slime/slime/backends/megatron_utils/model.py
```

Required behavior:

1. `--save-hf-only` skips Megatron resume checkpoint saving.
2. `--save-hf "$RUN_DIR/hf_checkpoints/rollout_{rollout_id}"` writes a full HF checkpoint.
3. HF save must fail if no GiB-level weight files are produced.
4. For Qwen3.5-4B checkpoints where bridge export omits source-only `mtp.*` tensors, the saver fills missing source tensors from the start HF checkpoint and writes a fresh safetensors index.

Before running this recipe on a fresh worker, verify:

```bash
python scripts/check_hf_checkpoint.py \
  /path/to/hf_checkpoints/rollout_49
```

Expected result:

```text
weight_file_count > 0
weight_size_gib > 1
ok = true
```

If a saved checkpoint directory is about 20MB and only contains tokenizer/config files, the runtime patch is missing or broken.
