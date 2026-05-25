<p align="center">
  <img src="../figures/welcome.png" width="80%" alt="AgentDoG Welcome"/>
</p>

<p align="center">
  🤗 <a href="https://huggingface.co/collections/AI45Research/agentdog"><b>Hugging Face</b></a>&nbsp&nbsp | &nbsp&nbsp
  🤖 <a href="https://www.modelscope.cn/collections/Shanghai_AI_Laboratory/AgentDoG">ModelScope</a>&nbsp&nbsp | &nbsp&nbsp
  📄 <a href="https://arxiv.org/pdf/2601.18491">Technical Report</a>&nbsp&nbsp | &nbsp&nbsp
  🌐 <a href="https://ai45lab.github.io/AgentDoG/">Project Page</a>&nbsp&nbsp | &nbsp&nbsp
  📘 <a href="https://example.com/AgentDoG-docs">Documentation</a>
</p>

Visit our Hugging Face or ModelScope organization (click links above), search checkpoints with names starting with `AgentDoG-`, and you will find all you need! Enjoy!

# AgentDoG


## Introduction

**AgentDoG** is a risk-aware evaluation and guarding framework for autonomous agents. It focuses on *trajectory-level risk assessment*, aiming to determine whether an agent’s execution trajectory contains safety risks under diverse application scenarios. Unlike single-step content moderation or final-output filtering, AgentDoG analyzes the full execution trace of tool-using agents to detect risks that emerge mid-trajectory.

- 🧭 **Trajectory-Level Monitoring:** evaluates multi-step agent executions spanning observations, reasoning, and actions.
- 🧩 **Taxonomy-Guided Diagnosis:** provides fine-grained risk labels (risk source, failure mode, and real-world harm) to explain why unsafe behavior occurs. More crucially, AgentDoG diagnoses the root cause of a specific action, tracing it to specific planning steps or tool selections.
- 🛡️ **Flexible Use Cases:** can serve as a benchmark, a risk classifier for trajectories, or a guard module in agent systems.
- 🥇 **State-of-the-Art Performance:** Outperforms existing approaches on R-Judge, ASSE-Safety, and ATBench.
<p align="center">
  <img src="../figures/binary_performance.png" width="95%">
</p>

<p align="center">
  <img src="../figures/fined_performance.png" width="95%">
</p>

---

## Basic Information

| Name | Parameters | BaseModel | Download |
|------|------------|-----------|----------|
| AgentDoG-Qwen3-4B | 4B |  Qwen3-4B-Instruct-2507 | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentDoG-Qwen3-4B) |
| AgentDoG-Qwen2.5-7B | 7B |  Qwen2.5-7B-Instruct | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentDoG-Qwen2.5-7B) |
| AgentDoG-Llama3.1-8B | 8B | Llama3.1-8B-Instruct | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentDoG-Llama3.1-8B) |
| AgentDoG-FG-Qwen3-4B | 4B | Qwen3-4B-Instruct-2507 | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentDoG-FG-Qwen3-4B) |
| AgentDoG-FG-Qwen2.5-7B | 7B | Qwen2.5-7B-Instruct | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentDoG-FG-Qwen2.5-7B) |
| AgentDoG-FG-Llama3.1-8B | 8B | Llama3.1-8B-Instruct | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentDoG-FG-Llama3.1-8B) |

For more details, please refer to [Technical Report](https://arxiv.org/pdf/2601.18491).

---

## 📚 Dataset: ATBench

We release **ATBench (Agent Trajectory Safety and Security Benchmark)** for trajectory-level safety evaluation and fine-grained risk diagnosis.

- **Download**: 🤗 [Hugging Face Datasets](https://huggingface.co/datasets/AI45Research/ATBench)
- **Scale**: 500 trajectories (250 safe / 250 unsafe), ~8.97 turns per trajectory (~4486 turn interactions)
- **Tools**: 1575 unique tools appearing in trajectories; an independent unseen-tools library with 2292 tool definitions (no overlap with training tools)
- **Labels**: binary `safe`/`unsafe`; unsafe trajectories additionally include fine-grained labels (Risk Source, Failure Mode, Real-World Harm)

---

## ✨ Safety Taxonomy
We adopt a unified, three-dimensional safety taxonomy for agentic systems. It organizes risks along three orthogonal axes, answering: why a risk arises (risk source), how it manifests in behavior (failure mode), and what harm it causes (real-world harm).

* **Risk Source**: where the threat originates in the agent loop, e.g., user inputs, environmental observations,
  external tools/APIs, or the agent's internal reasoning.
* **Failure Mode**: how the unsafe behavior is realized, such as flawed planning, unsafe tool usage,
  instruction-priority confusion, or unsafe content generation.
* **Real-World Harm**: the real-world impact, including privacy leakage, financial loss, physical harm,
  security compromise, or broader societal/psychological harms.

In the current release, the taxonomy includes 8 risk-source categories, 14 failure modes, and 10 real-world harm categories, and is used for fine-grained labeling during training and evaluation.

---

## 🧠 Methodology

### Task Definition

<p align="center">
  <img src="../figures/agentdog_prompt_coarsegrained.png" width="49%" alt="Trajectory-level safety evaluation prompt"/>
  <img src="../figures/agentdog_prompt_finegrained.png" width="49%" alt="Fine-grained risk diagnosis prompt"/>
</p>
<p align="center"><em>Figure: Example task instructions for the two AgentDoG classification tasks (trajectory-level evaluation and fine-grained diagnosis).</em></p>

Prior works (e.g., LlamaGuard, Qwen3Guard) formulate safety moderation as classifying whether the **final output** in a multi-turn chat is safe. In contrast, **AgentDoG** defines a different task: **diagnosing an entire agent trajectory** to determine whether the agent exhibits any unsafe behavior at **any point** during execution.

Concretely, we consider two tasks:

- **Trajectory-level safety evaluation (binary).** Given an agent trajectory (a sequence of steps, each step containing an action and an observation), predict `safe`/`unsafe`. A trajectory is labeled `unsafe` if **any** step exhibits unsafe behavior; otherwise it is `safe`.
- **Fine-grained risk diagnosis.** Given an `unsafe` trajectory, additionally predict the tuple (**Risk Source**, **Failure Mode**, **Real-World Harm**).

**Prompting.** Trajectory-level evaluation uses (i) task definition, (ii) agent trajectory, and (iii) output format. Fine-grained diagnosis additionally includes the safety taxonomy for reference and asks the model to output the three labels line by line.

| Task | Prompt Components |
|------|-------------------|
| **Trajectory-level safety evaluation** | Task Definition + Agent Trajectory + Output Format |
| **Fine-grained risk diagnosis** | Task Definition + Safety Taxonomy + Agent Trajectory + Output Format |

###  Data Synthesis and Collection

We use a **taxonomy-guided** synthesis pipeline to generate realistic, multi-step agent trajectories. Each trajectory is conditioned on a sampled risk tuple (risk source, failure mode, real-world harm), then expanded into a coherent tool-augmented execution and filtered by quality checks.

<p align="center">
  <img src="../figures/data_synthesis_main.png" width="95%" alt="Data Synthesis Pipeline"/>
</p>
<p align="center"><em>Figure: Three-stage pipeline for multi-step agent safety trajectory synthesis.</em></p>

To reflect realistic agent tool use, our tool library is orders of magnitude larger than prior benchmarks. For example, it is about 86x, 55x, and 41x larger than R-Judge, ASSE-Safety, and ASSE-Security, respectively.

<p align="center">
  <img src="../figures/tool_comparison.png" width="90%" alt="Tool library size comparison"/>
</p>
<p align="center"><em>Figure: Tool library size compared to existing agent safety benchmarks.</em></p>

We also track the coverage of the three taxonomy dimensions (risk source, failure mode, and harm type) to ensure balanced and diverse risk distributions in our synthesized data.

<p align="center">
  <img src="../figures/distribution_comparison.png" width="90%" alt="Taxonomy distribution comparison"/>
</p>
<p align="center"><em>Figure: Distribution over risk source, failure mode, and harm type categories.</em></p>

### Training

Our guard models are trained with standard **supervised fine-tuning (SFT)** on trajectory demonstrations. Given a training set $\mathcal{D}_{\mathrm{train}}=\lbrace(x_i, y_i)\rbrace _{i=1}^n$, where $x_i$ is an agent trajectory and $y_i$ is the target output (binary `safe`/`unsafe`, and optionally fine-grained labels), we minimize the negative log-likelihood:

$$\mathcal{L}=-\sum_{(x_i,y_i)\in\mathcal{D}_{\text{train}}}\log p_{\theta}(y_i\mid x_i).$$

We fine-tuned multiple base models: **Qwen3-4B-Instruct-2507**, **Qwen2.5-7B-Instruct**, and **Llama3.1-8B-Instruct**.

---

## 📊 Performance Highlights

* Evaluated on **R-Judge**, **ASSE-Safety**, and **ATBench**
* Outperforms step-level baselines in detecting:

  * Long-horizon instruction hijacking
  * Tool misuse after benign prefixes
* Strong generalization across:

  * Different agent frameworks
  * Different LLM backbones
* Fine-grained label accuracy on ATBench (best of our FG models): Risk Source 82.0%, Failure Mode 32.4%, Harm Type 59.2%

Accuracy comparison (ours + baselines):

| Model                          | Type          | R-Judge | ASSE-Safety | ATBench |
| ----------------------------- | ------------- | ------- | ----------- | ------ |
| GPT-5.2                       | General       | 90.8    | 77.4        | 90.0   |
| Gemini-3-Flash                | General       | 95.2    | 75.9        | 75.6   |
| Gemini-3-Pro                  | General       | 94.3    | 78.5        | 87.2   |
| QwQ-32B                       | General       | 89.5    | 68.2        | 63.0   |
| Qwen3-235B-A22B-Instruct       | General       | 85.1    | 77.6        | 84.6   |
| LlamaGuard3-8B                | Guard         | 61.2    | 54.5        | 53.3   |
| LlamaGuard4-12B               | Guard         | 63.8    | 56.3        | 58.1   |
| Qwen3-Guard                   | Guard         | 40.6    | 48.2        | 55.3   |
| ShieldAgent                   | Guard         | 81.0    | 79.6        | 76.0   |
| **AgentDoG-4B (Ours)**        | Guard         | 91.8    | 80.4        | 92.8   |
| **AgentDoG-7B (Ours)**        | Guard         | 91.7    | 79.8        | 87.4   |
| **AgentDoG-8B (Ours)**        | Guard         | 78.2    | 81.1        | 87.6   |

Fine-grained label accuracy on ATBench (unsafe trajectories only):

| Model                               | Risk Source Acc | Failure Mode Acc | Harm Type Acc |
| ---------------------------------- | --------------- | ---------------- | ------------- |
| Gemini-3-Flash                     | 38.0            | 22.4             | 34.8          |
| GPT-5.2                            | 41.6            | 20.4             | 30.8          |
| Gemini-3-Pro                       | 36.8            | 17.6             | 32.0          |
| Qwen3-235B-A22B-Instruct-2507      | 19.6            | 17.2             | 38.0          |
| QwQ-32B                            | 23.2            | 14.4             | 34.8          |
| **AgentDoG-FG-4B (Ours)**          | 82.0            | 32.4             | 58.4          |
| **AgentDoG-FG-8B (Ours)**          | 81.6            | 31.6             | 57.6          |
| **AgentDoG-FG-7B (Ours)**          | 81.2            | 28.8             | 59.2          |

---

## 🚀 Getting Started

### Deployment (SGLang / vLLM)

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

### Examples

#### Option 1: OpenAI-Compatible API (SGLang / vLLM)

Recommended: use prompt templates in `prompts/` and run the example script in `examples/`.

**Binary trajectory moderation**
```bash
python examples/run_openai_moderation.py \
  --base-url http://localhost:8000/v1 \
  --model AI45Research/AgentDoG-Qwen3-4B \
  --trajectory examples/trajectory_sample.json \
  --prompt prompts/trajectory_binary.txt
```

**Fine-grained risk diagnosis**
```bash
python examples/run_openai_moderation.py \
  --base-url http://localhost:8000/v1 \
  --model AI45Research/AgentDoG-FG-Qwen3-4B \
  --trajectory examples/trajectory_sample.json \
  --prompt prompts/trajectory_finegrained.txt \
  --taxonomy prompts/taxonomy_finegrained.txt
```

#### Option 2: Transformers Direct Inference

You can also run inference directly using `transformers` without deploying a server:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from typing import Dict
import json

model_name = "AI45Research/AgentDoG-Qwen3-FG-4B"
# load the tokenizer and the model
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="auto"
)

def format_conversation_history(example: Dict) -> str:
    """
    Format the entire conversation history as a single text block.
    """
    history_parts = []

    # Add profile/context
    if "profile" in example and example["profile"]:
        history_parts.append(f"=== Agent Profile ===\n{example['profile']}\n")

    history_parts.append("=== Conversation History ===")

    # Format each round of conversation
    for round_idx, round in enumerate(example["contents"], 1):
        for turn in round:
            role = turn["role"]

            if role == "user":
                if turn.get("content"):
                    history_parts.append(f"\n[USER]: {turn['content']}")

            elif role == "agent":
                # Format agent thought and action
                agent_parts = []
                for k, v in turn.items():
                    if k != "role" and v:
                        agent_parts.append(f"[{k.upper()}]: {v.strip()}")
                if agent_parts:
                    history_parts.append(f"\n[AGENT]:\n" + "\n".join(agent_parts))

            elif role == "environment":
                if turn.get("content"):
                    history_parts.append(f"\n[ENVIRONMENT]: {turn['content']}")

    return "\n".join(history_parts)

# load taxonomy and prompt template
with open("prompts/taxonomy_finegrained.txt", "r") as f:
    CATEGORY_FINEGRAINED = f.read()

with open("prompts/trajectory_finegrained.txt", "r") as f:
    chat_template = f.read()

# load your trajectory
with open("examples/trajectory_sample.json", "r") as f:
    trajectory = json.load(f)

# prepare the model input
formatted_trajectory = format_conversation_history(trajectory)
messages = [
    {"role": "user", "content": chat_template.format(trajectory=formatted_trajectory, taxonomy=CATEGORY_FINEGRAINED)}
]
text = tokenizer.apply_chat_template(
    messages,
    tokenize=False
)
model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

# conduct text completion
generated_ids = model.generate(
    **model_inputs,
    max_new_tokens=128
)
output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()
content = tokenizer.decode(output_ids, skip_special_tokens=True)
print(content)
# Example output:
# unsafe
# Risk Source: Inherent Agent/LLM Failures
# Failure Mode: Procedural Deviation or Inaction
# Real World Harm: Reputational & Interpersonal Harm
```

---

## 🔍 Agentic XAI Attribution
We also introduce a novel hierarchical framework for Agentic Attribution, designed to unveil the internal drivers behind agent actions beyond simple failure localization. By decomposing interaction trajectories into pivotal components and fine-grained textual evidence, our approach explains why an agent makes specific decisions regardless of the outcome. This framework enhances the transparency and accountability of autonomous systems by identifying key factors such as memory biases and tool outputs.
### Case Study
To evaluate the effectiveness of the proposed agentic attribution framework, we conducted several case studies across diverse scenarios. The figure illustrates how our framework localizes decision drivers across four representative cases. The highlighted regions denote the historical components and fine-grained sentences identified by our framework as the primary decision drivers.


<p align="center">
  <img src="../figures/xai_attribution_agent_dog.png" width="95%" alt="xai attribution agent dog"/>
</p>
<p align="center"><em>Figure: Illustration of attribution results across two representative scenarios.</em></p>


<p align="center">
  <img src="../figures/xai_attribution_comparison.png" width="70%" alt="xai attribution comparison"/>
</p>
<p align="center"><em>Figure: Comparative attribution results between AgentDoG and Basemodel.</em></p>

<p align="center">
  <img src="../figures/attribution_marker_v2.gif" width="90%" alt="attribution marker v2"/>
</p>
<p align="center"><em>Figure: Demo of dynamic attribution.</em></p>

### Quick Start for Agentic Attribution

You can run the analysis in three steps:

#### Step 1: Trajectory-Level Attribution
Analyze the contribution of each conversation step.
```bash
python component_attri.py \
  --model_id "your_model_path" \
  --data_dir ./samples \
  --output_dir ./results
```

#### Step 2: Sentence-Level Attribution
Perform fine-grained analysis on the top-K most influential steps.
```bash
python sentence_attri.py \
  --model_id "your_model_path" \
  --traj_file ./samples/xx.json \
  --attr_file ./results/xx_attr_trajectory.json \
  --output_file ./results/xx_attr_sentence.json \
  --top_k 3
```

#### Step 3: Generate Visualization
Create an interactive HTML heatmap.
```bash
python case_plot_html.py \
  --original_traj_file ./samples/xx.json \
  --traj_attr_file ./results/xx_attr_trajectory.json \
  --sent_attr_file ./results/xx_attr_sentence.json \
  --output_file ./results/xx_visualization.html
```

##### One-Click Execution
To run the complete pipeline automatically, configure and run the shell script:
```bash
bash run_all_pipeline.sh
```


## 📁 Repository Structure

```text
AgentDoG/
├── README.md
├── figures/
├── prompts/
│   ├── trajectory_binary.txt
│   ├── trajectory_finegrained.txt
│   └── taxonomy_finegrained.txt
├── examples/
│   ├── run_openai_moderation.py
│   └── trajectory_sample.json
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

* **Edit prompt templates**: `prompts/trajectory_binary.txt`, `prompts/trajectory_finegrained.txt`
* **Update taxonomy labels**: `prompts/taxonomy_finegrained.txt`
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
