<p align="center">
  <img src="figures/welcome.png" width="80%" alt="AgentDoG Welcome"/>
</p>

<p align="center">
  🤗 <a href="https://huggingface.co/AI45Research/AgentGuard"><b>Hugging Face</b></a>&nbsp&nbsp | &nbsp&nbsp
  🤖 <a href="https://modelscope.cn/collections/AgentDoG-000000000000000000000000">ModelScope</a>&nbsp&nbsp | &nbsp&nbsp
  📄 <a href="https://github.com/AI45Lab/AgentGuard/blob/main/AgentDoG_Technical_Report.pdf">Technical Report</a>&nbsp&nbsp | &nbsp&nbsp
  🌐 <a href="https://example.com/AgentDoG-demo">Demo</a>&nbsp&nbsp | &nbsp&nbsp
  📘 <a href="https://example.com/AgentDoG-docs">Documentation</a>
</p>

Visit our Hugging Face or ModelScope organization (click links above), search checkpoints with names starting with `AgentDoG-`, and you will find all you need! Enjoy!

# AgentDoG

---

## Introduction

**AgentDoG** is a risk-aware evaluation and guarding framework for autonomous agents. It focuses on *trajectory-level risk assessment*, aiming to determine whether an agent’s execution trajectory contains safety risks under diverse application scenarios. Unlike single-step content moderation or final-output filtering, AgentDoG analyzes the full execution trace of tool-using agents to detect risks that emerge mid-trajectory.

- 🧭 **Trajectory-Level Monitoring:** evaluates multi-step agent executions spanning observations, reasoning, and actions.
- 🧩 **Taxonomy-Guided Diagnosis:** provides fine-grained risk labels (risk source, failure mode, and risk consequence) to explain why unsafe behavior occurs.
- 🛡️ **Flexible Use Cases:** can serve as a benchmark, a risk classifier for trajectories, or a guard module in agent systems.
- 🥇 **State-of-the-Art Performance:** Outperforms existing approaches on R-Judge, ASSE-Safety, and GooDoG.
<p align="center">
  <img src="figures/R-Judge.png" width="33%">
  <img src="figures/asse.png" width="33%">
  <img src="figures/GooDoG.png" width="33%">
</p>



---

## Basic Information

| Name | Type | Download |
|------|------|----------|
| AgentDoG-Gen-0.6B | Generative Guard | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentGuard) |
| AgentDoG-Gen-4B | Generative Guard | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentGuard) |
| AgentDoG-Gen-8B | Generative Guard | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentGuard) |
| AgentDoG-Stream-0.6B | Stream Guard | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentGuard) |

For more details, please refer to our [blog](https://example.com/AgentDoG-blog) and [Technical Report](https://example.com/AgentDoG-technical-report).

---

## ✨ Safety Taxonomy
We adopt a unified, three-dimensional safety taxonomy for agentic systems. It organizes risks along three orthogonal axes, answering: why a risk arises (risk source), how it manifests in behavior (failure mode), and what harm it causes(risk consequence).

* **Risk Source**: where the threat originates in the agent loop, e.g., user inputs, environmental observations,
  external tools/APIs, or the agent's internal reasoning.
* **Failure Mode**: how the unsafe behavior is realized, such as flawed planning, unsafe tool usage,
  instruction-priority confusion, or unsafe content generation.
* **Risk Consequence**: the real-world impact, including privacy leakage, financial loss, physical harm,
  security compromise, or broader societal/psychological harms.

In the current release, the taxonomy includes 8 risk-source categories, 14 failure modes, and 10 risk-consequence categories, and is used for fine-grained labeling during training and evaluation.

---

## 🧠 Methodology

### Task Definition

<p align="center">
  <img src="figures/agentguard_eg.png" width="80%" alt="AgentDoG Task Example"/>
</p>
<p align="center"><em>Figure: Example task input for AgentDoG. The model analyzes the full trajectory and outputs a safety label with fine-grained categorization.</em></p>

Prior works (e.g., LlamaGuard, Qwen3Guard) formulate safety moderation as classifying whether the **final output** in a multi-turn chat is safe. In contrast, **AgentDoG** defines a different task: **diagnosing an entire agent trajectory** to determine whether the agent exhibits any unsafe behavior at **any point** during execution.

The input prompt consists of four components:

| Component | Description |
|-----------|-------------|
| **Task Definition** | Instructs the model to evaluate the trajectory for unsafe actions |
| **Safety Taxonomy** | Provides risk sources/triggers and failure modes as an analytical framework |
| **Agent Trajectory** | The multi-turn execution trace including user, agent, and environment interactions |
| **Output Specification** | Requires the model to output `safe` or `unsafe`, with fine-grained subtype labels for unsafe cases |

###  Data Synthesis and Collection

We use a **taxonomy-guided** synthesis pipeline to generate realistic, multi-step agent trajectories. Each trajectory is conditioned on a sampled risk tuple (risk source, failure mode, risk consequence), then expanded into a coherent tool-augmented execution and filtered by quality checks.

<p align="center">
  <img src="figures/data_synthesis_main.png" width="95%" alt="Data Synthesis Pipeline"/>
</p>
<p align="center"><em>Figure: Three-stage pipeline for multi-step agent safety trajectory synthesis.</em></p>

To reflect realistic agent tool use, our tool library is orders of magnitude larger than prior benchmarks. For example, it is about 86x, 55x, and 41x larger than R-Judge, ASSE-Safety, and ASSE-Security, respectively.

<p align="center">
  <img src="figures/tool_comparison.png" width="90%" alt="Tool library size comparison"/>
</p>
<p align="center"><em>Figure: Tool library size compared to existing agent safety benchmarks.</em></p>

We also track the coverage of the three taxonomy dimensions (risk source, failure mode, and harm type) to ensure balanced and diverse risk distributions in our synthesized data.

<p align="center">
  <img src="figures/distribution_comparison.png" width="90%" alt="Taxonomy distribution comparison"/>
</p>
<p align="center"><em>Figure: Distribution over risk source, failure mode, and harm type categories.</em></p>

### Training

---

## 📊 Performance Highlights

* Evaluated on **R-Judge**, **ASSE-Safety**, and **GooDoG**
* Outperforms step-level baselines in detecting:

  * Long-horizon instruction hijacking
  * Tool misuse after benign prefixes
* Strong generalization across:

  * Different agent frameworks
  * Different LLM backbones
* Fine-grained accuracy on GooDoG: Risk Source **80.8%**, Harm Type **60.0%**

Accuracy comparison (ours + baselines):

| Model                          | Type          | R-Judge | ASSE-Safety | GooDoG |
| ----------------------------- | ------------- | ------- | ----------- | ------ |
| **AgentDoG (Ours)**           | Guard         | **90.4** | **81.1**    | **85.6** |
| GPT-5.2                       | General       | 83.5    | 79.5        | 89.2   |
| Gemini-3-Flash                | General       | 93.6    | 81.5        | 94.4   |
| Gemini-3-Pro                  | General       | 93.8    | 81.1        | 95.2   |
| QwQ-32B                       | General       | 86.9    | 75.3        | 80.2   |
| Qwen3-235B-A22B-Instruct       | General       | 75.5    | 79.0        | 91.0   |
| LlamaGuard3-8B                | Guard         | 61.2    | 54.5        | 53.3   |
| LlamaGuard4-12B               | Guard         | 63.8    | 56.3        | 58.1   |
| Qwen3-Guard                   | Guard         | 40.6    | 48.2        | 55.3   |
| ShieldAgent                   | Guard         | 81.0    | 79.6        | 76.0   |

---

## 🚀 Getting Started

### Installation

```bash
git clone https://github.com/your-org/AgentGuard.git
cd AgentGuard
pip install -r requirements.txt
```

### Basic Usage

```python
from agentguard import Guard

guard = Guard(model="agentguard-base")
result = guard.evaluate(trajectory)

print(result.is_unsafe)
print(result.risk_type)
print(result.failure_mode)
```

---

## 🧪 Evaluation

To reproduce experiments:

```bash
python scripts/evaluate.py \
  --dataset r-judge \
  --model agentguard-base
```

Supported datasets:

* R-Judge
* ASSE-Safety
* GooDoG (ToolBench)

---

## Agentic XAI Attribution
We also introduce a novel hierarchical framework for Agentic Attribution, designed to unveil the internal drivers behind agent actions beyond simple failure localization. By decomposing interaction trajectories into pivotal components and fine-grained textual evidence, our approach explains why an agent makes specific decisions regardless of the outcome. This framework enhances the transparency and accountability of autonomous systems by identifying key factors such as memory biases and tool outputs.
### Case Study
To evaluate the effectiveness of the proposed agentic attribution framework, we conducted several case studies across diverse scenarios. The figure illustrates how our framework localizes decision drivers across four representative cases. The highlighted regions denote the historical components and fine-grained sentences identified by our framework as the primary decision drivers.

<p align="center">
  <img src="figures/agent_xai_fig_exp_case.jpg" width="95%" alt="Data Synthesis Pipeline"/>
</p>
<p align="center"><em>Figure: Illustration of attribution results across four representative scenarios.</em></p>



### Quick Start
#### Data Preparation
Ensure your input data is a JSON file containing a trajectory (or trace) list:
```json
{
  "trajectory": [
    {"role": "system", "content": "System prompt..."},
    {"role": "user", "content": "User query..."},
    {"role": "assistant", "content": "Agent response..."},
    {"role": "tool", "content": "Tool output..."}
  ]
}
```
#### Run Analysis Pipeline
You can run the analysis in three steps:

##### Step 1: Trajectory-Level Attribution \
Analyze the contribution of each conversation step.
```bash
python component_attri.py \
  --model_id meta-llama/Meta-Llama-3.1-70B-Instruct \
  --data_dir ./data \
  --output_dir ./results
```
##### Step 2: Sentence-Level Attribution \
Perform fine-grained analysis on the top-K most influential steps.
```bash
python sentence_attri.py \
  --model_id meta-llama/Meta-Llama-3.1-70B-Instruct \
  --attr_file ./results/case1_attr.json \
  --traj_file ./data/case1.json \
  --top_k 3
```


##### Step 3: Generate Visualization \
Create an interactive HTML heatmap.
```bash
python case_plot_html.py \
  --traj_attr_file ./results/case_attr.json \
  --sent_attr_file ./results/case_attr_sentence.json \
  --original_traj_file ./data/case.json \
  --output_file ./results/visualization.html
```

##### One-Click Execution \
To run the complete pipeline automatically, configure and run the shell script:
```bash
bash run_all_pipeline.sh
```


## 📁 Repository Structure

```
AgentGuard/
├── agentguard/
│   ├── models/
│   ├── data/
│   ├── taxonomy/
│   └── guard.py
├── scripts/
│   ├── evaluate.py
│   └── preprocess.py
├── benchmarks/
├── README.md
└──requirements.txt
```

---

## 🛠️ Customization

* **Add new risk types**: `taxonomy/`
* **Support new agent formats**: implement a trajectory parser
* **Plug in new models**: follow `models/base.py`

---

## 📜 License

This project is released under the **Apache 2.0 License**.

---

## 📖 Citation

If you use AgentGuard in your research, please cite:

```bibtex
@article{,
  title={AgentGuard: Trajectory-Level Risk Assessment for Autonomous Agents},
  author={Anonymous},
  year={2025}
}
```

---

## 🤝 Acknowledgements

This project builds upon prior work in agent safety, trajectory evaluation, and risk-aware AI systems.
