# APP1 Agentic Safety SFT

This repository provides a reproducible recipe for supervised fine-tuning Qwen3.5-4B on the APP1 Agentic Safety SFT dataset.

Dataset: https://huggingface.co/datasets/AI45Research/APP1-Agentic-Safety-SFT-Data

The dataset contains 78,705 Qwen3.5-native tool-use conversations, including 50K benign utility/tool-use examples and 28,705 agentic safety examples. The safety portion covers harmful-user instructions, unsafe tool-use behaviors, indirect prompt-injection cases, over-refusal repair data, and targeted agentic safety repair examples.

## Setup

Install LLaMA-Factory following its official instructions:

```bash
git clone https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory
pip install -e ".[torch,metrics]"
```

Install Hugging Face Hub utilities:

```bash
pip install -U huggingface_hub
```

## Download Data

Download the dataset from Hugging Face:

```bash
huggingface-cli download \
  AI45Research/APP1-Agentic-Safety-SFT-Data \
  --repo-type dataset \
  --local-dir data/app1_agentic_safety_sft
```

Copy or symlink the JSON file into LLaMA-Factory's `data/` directory:

```bash
cp data/app1_agentic_safety_sft/agentic_safety_sft.json \
  data/agentic_safety_sft.json
```

The expected dataset size is:

```text
78,705 examples
```

## Register Dataset

Add the following entry to `data/dataset_info.json`:

```json
{
  "agentic_safety_sft": {
    "file_name": "agentic_safety_sft.json",
    "formatting": "sharegpt",
    "columns": {
      "messages": "messages"
    },
    "tags": {
      "role_tag": "role",
      "content_tag": "content",
      "user_tag": "user",
      "assistant_tag": "assistant",
      "system_tag": "system"
    }
  }
}
```

## Training Configuration

Create `train_qwen35_4b_agentic_safety_sft.yaml`:

```yaml
### model
model_name_or_path: /path/to/Qwen3.5-4B
trust_remote_code: true

### method
stage: sft
do_train: true
finetuning_type: full
deepspeed: examples/deepspeed/ds_z2_config.json

### dataset
dataset: agentic_safety_sft
template: qwen3_5_nothink
cutoff_len: 16384
overwrite_cache: true
preprocessing_num_workers: 32
dataloader_num_workers: 8

### output
output_dir: outputs/qwen35_4b_agentic_safety_sft
logging_steps: 10
save_strategy: "no"
save_total_limit: 1
save_only_model: true
plot_loss: true
overwrite_output_dir: true
report_to: none

### train
per_device_train_batch_size: 2
gradient_accumulation_steps: 8
learning_rate: 5.0e-6
num_train_epochs: 2.0
lr_scheduler_type: cosine
warmup_ratio: 0.03
bf16: true
gradient_checkpointing: true
ddp_timeout: 180000000
resume_from_checkpoint: null
```

## Start Training

Run full-parameter SFT on 4 GPUs:

```bash
CUDA_VISIBLE_DEVICES=0,1,2,3 \
FORCE_TORCHRUN=1 \
llamafactory-cli train train_qwen35_4b_agentic_safety_sft.yaml
```

The effective global batch size is:

```text
4 GPUs × per_device_train_batch_size 2 × gradient_accumulation_steps 8 = 64
```

The recipe trains for 2 epochs with learning rate `5e-6`, cosine scheduling, warmup ratio `0.03`, bf16 precision, gradient checkpointing, and DeepSpeed ZeRO-2.

## Notes

- The dataset is already converted to the Qwen3.5-native tool-call format.
- The training template is `qwen3_5_nothink`, matching the non-thinking setting used in our experiments.
- The recipe uses full-parameter SFT rather than LoRA.
- Only the final model is saved because `save_strategy: "no"` and `save_only_model: true` are enabled.
