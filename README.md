# AgentGuard

**AgentGuard** is a risk-aware evaluation and guarding framework for autonomous agents. It focuses on *trajectory-level risk assessment*, aiming to determine whether an agent’s execution trajectory contains safety risks under diverse application scenarios.

---

## 🔍 Overview

Autonomous agents (e.g., tool-using LLM agents, mobile agents, web agents) often execute multi-step trajectories consisting of observations, reasoning, and actions. Existing safety mechanisms mainly focus on **single-step content moderation** or **final-output filtering**, which are insufficient for capturing risks emerging *during execution*.

**AgentGuard** addresses this gap by:



AgentGuard can be used as:

* A **benchmark** for agent safety evaluation
* A **risk classifier** for agent trajectories
* A **guard module** integrated into agent systems

| Name                  | Type     |Download                                                                                                                                                                        |
|-----------------------------|----------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| AgentGuard-0.6B         | Generative Guard    | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentGuard  )                                |
| AgentGuard-Gen-4B         | Generative Guard     | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentGuard  )                                           |
| AgentGuard-8B         | Generative Guard     | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentGuard  )                              |
|AgentGuard-Stream-0.6B         | Stream Guard     | 🤗 [Hugging Face](https://huggingface.co/AI45Research/AgentGuard  )                               |


For more details, please refer to our [Technical Report](https://github.com//blob/main/_Technical_Report.pdf).
---

## ✨ Safety Taxonomy


---

## 🧠 Methodology

### Task Definition

Prior works (e.g., LlamaGuard, Qwen3Guard) formulate safety moderation as classifying whether the **final output** in a multi-turn chat is safe. In contrast, **AgentGuard** defines a different task: **diagnosing an entire agent trajectory** to determine whether the agent exhibits any unsafe behavior at **any point** during execution.

The input prompt consists of four components:

| Component | Description |
|-----------|-------------|
| **Task Definition** | Instructs the model to evaluate the trajectory for unsafe actions |
| **Safety Taxonomy** | Provides risk sources/triggers and failure modes as an analytical framework |
| **Agent Trajectory** | The multi-turn execution trace including user, agent, and environment interactions |
| **Output Specification** | Requires the model to output `safe` or `unsafe`, with fine-grained subtype labels for unsafe cases |

<p align="center">
  <img src="figures/agentguard_eg.png" width="80%" alt="AgentGuard Task Example"/>
</p>
<p align="center"><em>Figure: Example task input for AgentGuard. The model analyzes the full trajectory and outputs a safety label with fine-grained categorization.</em></p>

###  Data Synthesis and Collection


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
