# AgentGuard

**AgentGuard** is a risk-aware evaluation and guarding framework for autonomous agents. It focuses on *trajectory-level risk assessment*, aiming to determine whether an agent’s execution trajectory contains safety risks under diverse application scenarios.

---

## 🔍 Overview

Autonomous agents (e.g., tool-using LLM agents, mobile agents, web agents) often execute multi-step trajectories consisting of observations, reasoning, and actions. Existing safety mechanisms mainly focus on **single-step content moderation** or **final-output filtering**, which are insufficient for capturing risks emerging *during execution*.

**AgentGuard** addresses this gap by providing **trajectory-level safety assessment** that monitors the entire execution process, not just final outputs.

AgentGuard can be used as:

* A **benchmark** for agent safety evaluation
* A **risk classifier** for agent trajectories
* A **guard module** integrated into agent systems

| Name | Type | Download |
|------|------|----------|
| AgentGuard-Gen-0.6B | Generative Guard | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentGuard) |
| AgentGuard-Gen-4B | Generative Guard | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentGuard) |
| AgentGuard-Gen-8B | Generative Guard | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentGuard) |
| AgentGuard-Stream-0.6B | Stream Guard | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentGuard) |

For more details, please refer to our [Technical Report](https://github.com//blob/main/_Technical_Report.pdf).

---

## ✨ Safety Taxonomy


---

## 🧠 Methodology

### Task Definition

<p align="center">
  <img src="figures/agentguard_eg.png" width="80%" alt="AgentGuard Task Example"/>
</p>
<p align="center"><em>Figure: Example task input for AgentGuard. The model analyzes the full trajectory and outputs a safety label with fine-grained categorization.</em></p>

Prior works (e.g., LlamaGuard, Qwen3Guard) formulate safety moderation as classifying whether the **final output** in a multi-turn chat is safe. In contrast, **AgentGuard** defines a different task: **diagnosing an entire agent trajectory** to determine whether the agent exhibits any unsafe behavior at **any point** during execution.

The input prompt consists of four components:

| Component | Description |
|-----------|-------------|
| **Task Definition** | Instructs the model to evaluate the trajectory for unsafe actions |
| **Safety Taxonomy** | Provides risk sources/triggers and failure modes as an analytical framework |
| **Agent Trajectory** | The multi-turn execution trace including user, agent, and environment interactions |
| **Output Specification** | Requires the model to output `safe` or `unsafe`, with fine-grained subtype labels for unsafe cases |

###  Data Synthesis and Collection

We introduce a **taxonomy-guided** agent risk trajectory synthesis approach to generate high-quality training data. The key idea is to steer data generation with a three-dimensional risk taxonomy (risk source, failure mode, risk consequence) and perform targeted sampling to systematically cover the risk space.

<p align="center">
  <img src="figures/data_synthesis_main.png" width="95%" alt="Data Synthesis Pipeline"/>
</p>
<p align="center"><em>Figure: Three-stage pipeline for multi-step agent safety trajectory synthesis.</em></p>

#### Stage 1: Planning

For each trajectory, we first sample a risk configuration tuple from the safety taxonomy and determine the safety outcome (safe or unsafe). Then the planner constructs a coherent multi-step task plan via:
- **Phase 1**: Design a task and analyze how risk can be naturally embedded (Chain-of-Thought)
- **Phase 2**: Produce a structured execution plan with task description, tool subset, step sequence, and risk injection point

#### Stage 2: Trajectory Synthesis

The Orchestrator coordinates multiple generation modules to transform plans into concrete trajectories:

| Module | Function |
|--------|----------|
| **Query Generator** | Generates initial user queries; applies targeted rewriting for certain risk sources |
| **Tool Call Simulator** | Synthesizes tool call arguments and generates plausible tool outputs |
| **Agent Response Generator** | Produces agent responses in Normal/Defense/Post-Risk modes |
| **Reason Generator** | Generates concise safety outcome summaries |

#### Stage 3: Quality Control

A dual-layer quality control procedure ensures data quality:

| Layer | Checks |
|-------|--------|
| **Rule-based Validators** | Turn structure, tool invocation validity, step coherence, readability |
| **LLM-based Judge** | Risk taxonomy label consistency, attack success verification for unsafe trajectories |

### Training


## 📊 Performance Highlights

> *(Fill in with your experimental results)*

* Evaluated on **AgentJudge**, **SAFE**, and internal benchmarks
* Outperforms step-level baselines in detecting:

  * Long-horizon instruction hijacking
  * Tool misuse after benign prefixes
* Strong generalization across:

  * Different agent frameworks
  * Different LLM backbones

Example metrics:

| Dataset    | Accuracy | F1 (Unsafe) | AUROC |
| ---------- | -------- | ----------- | ----- |
| AgentJudge | XX.X     | XX.X        | XX.X  |
| SAFE       | XX.X     | XX.X        | XX.X  |

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
  --dataset agentjudge \
  --model agentguard-base
```

Supported datasets:

* AgentJudge
* SAFE
* Custom JSON trajectories

---


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
└── requirements.txt
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
