# AgentDoG 1.0 Getting Started

This page keeps the original AgentDoG 1.0 deployment and inference commands. For AgentDoG 1.5, please use [getting_started_v1_5.md](getting_started_v1_5.md).

## Deployment (SGLang / vLLM)

For deployment, you can use `sglang>=0.4.6` or `vllm>=0.10.0` to create an OpenAI-compatible API endpoint:

**SGLang**
```bash
python -m sglang.launch_server --model-path AI45Research/AgentDoG-Qwen3-4B --port 30000 --context-length 16384
python -m sglang.launch_server --model-path AI45Research/AgentDoG-FG-Qwen3-4B --port 30001 --context-length 16384
```

**vLLM**
```bash
vllm serve AI45Research/AgentDoG-Qwen3-4B --port 8000 --max-model-len 16384
vllm serve AI45Research/AgentDoG-FG-Qwen3-4B --port 8001 --max-model-len 16384
```

## Examples

### OpenAI-Compatible API (SGLang / vLLM)

Recommended: use prompt templates in `prompts/v1.0/` and run the example script in `examples/`.

**Binary trajectory moderation**
```bash
python examples/run_openai_moderation.py \
  --base-url http://localhost:8000/v1 \
  --model AI45Research/AgentDoG-Qwen3-4B \
  --trajectory examples/trajectory_sample.json \
  --prompt prompts/v1.0/trajectory_binary.txt
```

**Fine-grained risk diagnosis**
```bash
python examples/run_openai_moderation.py \
  --base-url http://localhost:8000/v1 \
  --model AI45Research/AgentDoG-FG-Qwen3-4B \
  --trajectory examples/trajectory_sample.json \
  --prompt prompts/v1.0/trajectory_finegrained.txt \
  --taxonomy prompts/v1.0/taxonomy_finegrained.txt
```
