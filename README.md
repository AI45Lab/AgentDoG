<p align="center">
  <img src="figures/welcome.png" width="80%" alt="AgentDoG Welcome"/>
</p>

<p align="center">
  🤗 <a href="https://huggingface.co/collections/AI45Research/agentdog"><b>Hugging Face</b></a>&nbsp;&nbsp; | &nbsp;&nbsp;
  🤖 <a href="https://www.modelscope.cn/collections/Shanghai_AI_Laboratory/AgentDoG">ModelScope</a>&nbsp;&nbsp; | &nbsp;&nbsp;
  📄 <a href="https://arxiv.org/pdf/2601.18491">AgentDoG 1.0 Technical Report</a>&nbsp;&nbsp; | &nbsp;&nbsp;
  📄 <a href="#">AgentDoG 1.5 Technical Report</a>&nbsp;&nbsp; | &nbsp;&nbsp;
  🌐 <a href="https://ai45lab.github.io/AgentDoG/">Project Page</a>
</p>

Visit our Hugging Face or ModelScope organization (click links above), search checkpoints with names starting with `AgentDoG-`, and you will find all you need! Enjoy!


# AgentDoG Family: Towards Diagnostic Guardrail and Scalable Alignment for AI Agent Safety and Security

## News

- `2026/xx/xx`: AgentDoG 1.5 is coming soon, introducing lightweight and scalable guardrail models for trajectory-level agent safety.
- `2026/xx/xx`: We extend ATBench into the ATBench Family, covering general tool-use agents, OpenClaw-style stateful agents, and Codex-style repository agents.
- `2026/xx/xx`: AgentDoG 1.5 supports two application settings: safety agentic SFT/RL and online agent safety guardrails.
- `2026/01/26`: We have released [AgentDoG 1.0](examples/readme_v1.md), a diagnostic guardrail framework for AI agent safety and security.

## Introduction

**AgentDoG 1.5** is a cost-effective and extensible **Diagnostic Guardrail** for trajectory-level agent safety assessment, building on the foundation of AgentDoG 1.0. It expands agent safety diagnosis from fixed trajectory classification toward a scalable framework for modern agentic systems with long-horizon planning, tool-mediated execution, and complex environment interaction.

- 🧩 **Extensible Taxonomy for Agentic Safety Diagnosis:** expands the original safety taxonomy into a flexible framework that captures emerging risks from modern agentic AI systems, including long-horizon planning, tool-mediated execution, and complex environment interaction.
- 📚 **Extensible ATBench Family:** refines ATBench into a trajectory-level benchmark family with 1,000 audited trajectories, 2,084 available tools, 1,954 unique invoked tools, and an average of 9.01 turns and 3.95k tokens per trajectory, further instantiated by ATBench-Codex and ATBench-Claw.
- 🛡️ **Cost-Effective Diagnostic Guardrail Models:** trains AgentDoG 1.5 through an efficient data preparation and training pipeline with around 1k SFT trajectories and several thousand RL samples, covering a high-performing 4B variant and lightweight 0.8B and 2B variants.
- 🚀 **Practical Agent Safety Applications:** demonstrates AgentDoG 1.5 in safety-aware agentic SFT/RL and online agent safety monitoring, highlighting its use as a practical safety component for deployed agentic AI systems.

<p align="center">
  <img src="figures/binary_performance.png" width="95%">
</p>

---

## Model Zoo

### AgentDoG 1.5
| Name | Parameters | Base Model | HF Link | ModelScope Link |
|------|------------|------------|---------|-----------------|
| AgentDoG1.5-Unified-Qwen3.5-4B | 4B | Qwen3.5 | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentDoG1.5-unified-Qwen3.5-4B) | Coming soon |
| AgentDoG1.5-Qwen3.5-0.8B | 0.8B | Qwen3.5 | Coming soon | Coming soon |
| AgentDoG1.5-Qwen3.5-2B | 2B | Qwen3.5 | Coming soon | Coming soon |
| AgentDoG1.5-Qwen3.5-4B | 4B | Qwen3.5 | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentDoG-1.5-Qwen3.5-4B) | Coming soon |
| AgentDoG1.5-FG-Qwen3.5-0.8B | 0.8B | Qwen3.5 | Coming soon | Coming soon |
| AgentDoG1.5-FG-Qwen3.5-2B | 2B | Qwen3.5 | Coming soon | Coming soon |
| AgentDoG1.5-FG-Qwen3.5-4B | 4B | Qwen3.5 | Coming soon | Coming soon |

### AgentDoG 1.0

| Name | Parameters | Base Model | HF Link | ModelScope Link |
|------|------------|------------|---------|-----------------|
| AgentDoG-Qwen3-4B | 4B | Qwen3-4B-Instruct-2507 | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentDoG-Qwen3-4B) | 🤖 [ModelScope](https://www.modelscope.cn/collections/Shanghai_AI_Laboratory/AgentDoG) |
| AgentDoG-Qwen2.5-7B | 7B | Qwen2.5-7B-Instruct | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentDoG-Qwen2.5-7B) | 🤖 [ModelScope](https://www.modelscope.cn/collections/Shanghai_AI_Laboratory/AgentDoG) |
| AgentDoG-Llama3.1-8B | 8B | Llama3.1-8B-Instruct | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentDoG-Llama3.1-8B) | 🤖 [ModelScope](https://www.modelscope.cn/collections/Shanghai_AI_Laboratory/AgentDoG) |
| AgentDoG-FG-Qwen3-4B | 4B | Qwen3-4B-Instruct-2507 | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentDoG-FG-Qwen3-4B) | 🤖 [ModelScope](https://www.modelscope.cn/collections/Shanghai_AI_Laboratory/AgentDoG) |
| AgentDoG-FG-Qwen2.5-7B | 7B | Qwen2.5-7B-Instruct | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentDoG-FG-Qwen2.5-7B) | 🤖 [ModelScope](https://www.modelscope.cn/collections/Shanghai_AI_Laboratory/AgentDoG) |
| AgentDoG-FG-Llama3.1-8B | 8B | Llama3.1-8B-Instruct | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentDoG-FG-Llama3.1-8B) | 🤖 [ModelScope](https://www.modelscope.cn/collections/Shanghai_AI_Laboratory/AgentDoG) |

For more details, please refer to the AgentDoG technical reports.

---
## ✨ Safety Taxonomy

AgentDoG adopts a three-dimensional safety taxonomy for trajectory-level agent safety diagnosis: **Risk Source**, **Failure Mode**, and **Real-world Harm**. This taxonomy separates where a risk enters the trajectory, how it manifests in the agent's behavior, and what consequence it may produce.

* **Risk Source**: where the risk comes from.
* **Failure Mode**: how the agent fails.
* **Real-world Harm**: what consequence the unsafe behavior may cause.

In AgentDoG 1.5, we reinterpret the taxonomy not as a static label space, but as a **shared diagnostic scaffold** for evolving agent execution settings. The three high-level dimensions remain fixed, while new settings can be supported through setting-specific customization and strengthened inherited categories.

<p align="center">
  <img src="figures/safety_taxonomy_overview_v1_5.png" width="95%" alt="Three-dimensional agentic safety taxonomy"/>
</p>

---

## ATBench Family

AgentDoG 1.5 extends the original ATBench into a benchmark family for trajectory-level agent safety. The ATBench Family keeps a unified diagnostic protocol while adapting to different agent execution environments.

| Benchmark | Agent Setting | Description | Download |
|-----------|---------------|-------------|----------|
| **ATBench** | General tool-use agents | The base trajectory-level safety benchmark inherited from AgentDoG 1.0. | 🤗 [Hugging Face](https://huggingface.co/datasets/AI45Research/ATBench) |
| **ATBench-Claw** | OpenClaw agents with stateful tool/skill execution | Extends the benchmark to persistent sessions, accumulated traces, and stateful tool execution. | 🤗 [Hugging Face](https://huggingface.co/datasets/AI45Research/ATBench-Claw) |
| **ATBench-Codex** | Codex-style repository and command execution agents | Extends the benchmark to repository modification, shell commands, file operations, and code-execution risks. | 🤗 [Hugging Face](https://huggingface.co/datasets/AI45Research/ATBench-Codex) |

ATBench Family is designed to evaluate whether a guardrail can generalize from general tool-use trajectories to specialized agent environments. It also demonstrates how the three-dimensional taxonomy can be customized for new settings while preserving the same diagnostic interface.

---

## AgentDoG 1.5

In response to the risks introduced by emerging agentic AI systems, we develop a rationale-enhanced and cost-efficient construction framework, equipping AgentDoG 1.5 with rationale-generation capability, improving its safety judgment accuracy, and supporting low-cost deployment.

### Building Pipeline

<p align="center">
  <img src="figures/building_pipeline_v1_5.png" width="95%" alt="AgentDoG 1.5 building pipeline"/>
</p>

### Evaluation

AgentDoG 1.5 is evaluated on R-Judge and ATBench using Accuracy, Precision, Recall, and F1-score. We compare against closed-source models, open-source models, guard models, and AgentDoG-series models.

| Model | R-Judge Acc | R-Judge Prec. | R-Judge Rec. | R-Judge F1 | ATBench Acc | ATBench Prec. | ATBench Rec. | ATBench F1 |
|-------|-------------|---------------|--------------|------------|-------------|---------------|--------------|------------|
| GPT-5.4 | 93.3 | 93.1 | 94.3 | 93.7 | 73.7 | 68.5 | 87.1 | 76.7 |
| Qwen3.5-397B-A17B | 85.6 | 81.3 | 94.5 | 87.4 | 66.8 | 65.5 | 70.2 | 67.8 |
| Qwen3.5-4B | 81.0 | 82.1 | 81.9 | 82.0 | 45.9 | 41.2 | 20.7 | 27.6 |
| LlamaGuard4-12B | 63.8 | 68.3 | 58.8 | 63.2 | 58.1 | 63.8 | 30.9 | 41.7 |
| Qwen3-Guard | 40.6 | 23.6 | 5.6 | 9.0 | 51.5 | 40.0 | 0.4 | 0.8 |
| AgentDoG-1.0-Qwen3-4B | 91.8 | 87.5 | 98.5 | 92.7 | 64.0 | 59.2 | 88.9 | 71.1 |
| AgentDoG-1.5-Qwen3.5-0.8B | 75.7 | 83.3 | 67.5 | 74.6 | 60.3 | 58.6 | 68.6 | 63.2 |
| AgentDoG-1.5-Qwen3.5-2B | 71.5 | 78.0 | 64.1 | 70.4 | 69.0 | 70.1 | 65.7 | 67.8 |
| AgentDoG-1.5-Llama3.1-8B | 75.5 | 68.6 | 98.8 | 81.0 | 70.9 | 67.1 | 81.2 | 73.5 |
| AgentDoG-1.5-Qwen3.5-4B | 92.2 | 91.7 | 93.7 | 92.7 | 72.4 | 69.2 | 80.3 | 74.3 |
| AgentDoG-1.5-Qwen3.5-4B-U | 90.4 | 93.9 | 87.6 | 90.6 | 78.4 | 79.8 | 75.7 | 77.7 |

Fine-grained diagnostic accuracy on ATBench is reported along the three taxonomy dimensions. Guard models are excluded because they only output binary labels.

| Model | Risk Source | Failure Mode | Real-world Harm |
|-------|-------------|--------------|-----------------|
| GPT-5.4 | 33.6 | 13.5 | 30.2 |
| GPT-5.2 | 29.5 | 12.0 | 26.8 |
| Gemini-3-Flash | 18.4 | 8.3 | 15.0 |
| Gemini-3.1-Pro | 24.8 | 12.6 | 18.5 |
| Qwen3.5-397B | 7.7 | 3.6 | 6.8 |
| AgentDoG-1.0-Qwen3-4B | 46.8 | 16.5 | 40.6 |
| AgentDoG-1.5-Qwen3.5-0.8B | 65.7 | 18.4 | 44.9 |
| AgentDoG-1.5-Qwen3.5-2B | 68.0 | 24.0 | 53.8 |
| AgentDoG-1.5-Llama3.1-8B | 72.9 | 24.6 | 52.5 |
| AgentDoG-1.5-Qwen3.5-4B | 75.2 | 27.5 | 62.9 |
| AgentDoG-1.5-Qwen3.5-4B-U | 24.1 | 9.5 | 28.4 |

Accuracy on ATBench-Codex and ATBench-Claw across model sizes. The x-axis uses dense model size and active parameters for MoE models; closed-source models are shown as high/low reference lines because their sizes are unavailable. Guard models use approximate backbone sizes with slight jitter, and Qwen3.5-0.8B/2B are omitted due to low strict-parser validity.

<p align="center">
  <img src="figures/codex-claw.png" width="95%" alt="ATBench-Codex and ATBench-Claw performance by model size"/>
</p>

---

## Application 1: Agentic Safety SFT & RL with AgentDoG 1.5

AgentDoG 1.5 can serve as a trajectory-level diagnostic evaluator for improving agent safety through supervised fine-tuning and reinforcement learning.

Application materials will be organized under [`App1/`](App1/).

### Evaluation Setup

AgentDoG 1.5 is used to evaluate safety behavior across multiple agentic benchmarks and environments, including harmful instruction following, tool-use safety, refusal behavior, and multi-step agent execution.

### Agentic SFT

AgentDoG 1.5 can filter and select high-quality safety data for agentic supervised fine-tuning. By evaluating generated trajectories, it helps construct a mixture of safety-critical and benign agentic data.

### Agentic RL

AgentDoG 1.5 can be integrated as an external safety evaluator in agentic reinforcement learning. It provides safety feedback for harmful behavior, unsafe tool usage, and safe refusal behavior.

---

## Application 2: AgentDoG 1.5 as Online Agentic Safety Guardrail

AgentDoG 1.5 can also be deployed as an online agent safety guardrail. During agent execution, it can inspect accumulated trajectories before pending actions or final visible responses and flag unsafe behavior before it reaches the user or environment.

**Guardrail Design.** AgentDoG 1.5 can be placed before high-risk actions or final replies. It takes the accumulated trajectory as input and returns a safety judgment, optionally with fine-grained diagnostic labels.

Application materials will be organized under [`App2/`](App2/).

<p align="center">
  <img src="figures/app2_online_guardrail_framework.png" width="95%" alt="App 2 online guardrail framework"/>
</p>

<p align="center">
  <a href="docs/figures/app2_online_guardrail_demo_30s.mp4">
    <img src="docs/figures/app2_online_guardrail_preview.gif" width="85%" alt="App 2 online guardrail demo preview"/>
  </a>
</p>
<p align="center">
  <a href="docs/figures/app2_online_guardrail_demo_30s.mp4">Lightweight demo of AgentDoG 1.5 as an online agent safety guardrail.</a>
</p>

---

## 🚀 Getting Started

AgentDoG 1.0 and AgentDoG 1.5 use different model checkpoints and prompt formats, so their deployment and inference instructions are maintained separately:

- [AgentDoG 1.5 Getting Started](examples/getting_started_v1_5.md)
- [AgentDoG 1.0 Getting Started](examples/getting_started_v1.md)

---

## 📁 Repository Structure

```text
AgentDoG/
├── README.md
├── figures/
├── docs/
│   ├── index.html
│   ├── style.css
│   ├── figures/
│   ├── v1/
│   │   └── index.html
│   └── v1_5/
│       └── index.html
├── prompts/
│   ├── v1.0/
│   │   ├── trajectory_binary.txt
│   │   ├── trajectory_finegrained.txt
│   │   └── taxonomy_finegrained.txt
│   └── v1.5/
│       ├── coarse_grained_moderation.txt
│       └── unified_safety_classification.txt
├── examples/
│   ├── getting_started_v1.md
│   ├── getting_started_v1_5.md
│   ├── readme_v1.md
│   ├── run_openai_moderation.py
│   └── trajectory_sample.json
├── App1/
│   └── README.md
├── App2/
│   └── README.md
├── AgenticXAI
│   ├── case_plot_html.py
│   ├── component_attri.py
│   ├── README.md
│   ├── run_all_pipeline.sh
│   ├── samples
│   │   ├── finance.json
│   │   ├── resume.json
│   │   └── transaction.json
│   └── sentence_attri.py
```

---

## 🛠️ Customization

* **Edit prompt templates**: `prompts/v1.0/trajectory_binary.txt`, `prompts/v1.0/trajectory_finegrained.txt`, `prompts/v1.5/coarse_grained_moderation.txt`, `prompts/v1.5/unified_safety_classification.txt`
* **Update taxonomy labels**: `prompts/v1.0/taxonomy_finegrained.txt`
* **Change runtime integration**: `examples/run_openai_moderation.py`

---

## 📜 License

This project is released under the **Apache 2.0 License**.

---

## 📖 Citation

If you use AgentDoG or ATBench in your research, please cite:

```bibtex
@article{liu2026agentdog,
  title={AgentDoG: A Diagnostic Guardrail Framework for AI Agent Safety and Security},
  author={Liu, Dongrui and Ren, Qihan and Qian, Chen and Shao, Shuai and Xie, Yuejin and Li, Yu and Yang, Zhonghao and Luo, Haoyu and Wang, Peng and Liu, Qingyu and others},
  journal={arXiv preprint arXiv:2601.18491},
  year={2026}
}

@article{li2026atbench,
  title={ATBench: A Diverse and Realistic Trajectory Benchmark for Long-Horizon Agent Safety},
  author={Li, Yu and Luo, Haoyu and Xie, Yuejin and Fu, Yuqian and Yang, Zhonghao and Shao, Shuai and Ren, Qihan and Qu, Wanying and Fu, Yanwei and Yang, Yujiu and others},
  journal={arXiv preprint arXiv:2604.02022},
  year={2026}
}

@misc{qian2026behind,
      title={The Why Behind the Action: Unveiling Internal Drivers via Agentic Attribution},
      author={Chen Qian and Peng Wang and Dongrui Liu and Junyao Yang and Dadi Guo and Ling Tang and Jilin Mei and Qihan Ren and Shuai Shao and Yong Liu and Jie Fu and Jing Shao and Xia Hu},
      year={2026},
      journal={arXiv preprint arXiv:2601.15075}
}
```

---

## 🤝 Acknowledgements

This project builds upon prior work in agent safety, trajectory evaluation, and risk-aware AI systems.
