---
tags:
  - agent-safety
  - guardrails
  - long-horizon
  - agentdog
---

<!-- TEMPLATE: Complete checkpoint-specific fields before publishing this as a model repository README.md. Do not publish the selection instructions below. -->

# AgentDoG 2.0 — CHECKPOINT NAME

## Model description

This checkpoint belongs to the AgentDoG 2.0 framework from Shanghai Artificial Intelligence Laboratory, which studies safety diagnosis and mitigation in long-horizon agent workflows.

**Checkpoint role:** REPLACE WITH ONE VERIFIED ROLE:

- **AgentDoG 2.0 guard:** structured trajectory-level safety judgments using the expanded taxonomy, without Chain-of-Thought generation.
- **AgentDoG-Jev:** structured safety decisions and normalized field confidences from a single forward pass, without autoregressive decoding.
- **AgentDoG-Step:** pre-execution assessment of a proposed action using the interaction history, with a short rationale and structured diagnosis.

The framework's taxonomy covers 18 risk sources, 21 failure modes, and 11 real-world harm categories. Specify which outputs this checkpoint supports.

## Checkpoint details and usage

Complete the exact base model, parameter count, revision, license, supported languages, required library versions, input schema, output schema, and checkpoint-specific loading example. For Jev, document the decision schema and decision-position mapping. For Step, provide interaction history and the candidate action without future execution results.

## Evaluation

Add results for this exact checkpoint, including benchmark version, metric definition, evaluation setting, and hardware for latency measurements. A benchmark average must identify its constituent datasets and averaging rule. Report safety and task-utility results separately where both are measured.

## Intended use and limitations

Use this checkpoint to support safety assessment in the documented agent setting. Predictions may miss unsafe behavior or reject safe actions; evaluate them in the target workflow before selecting intervention thresholds. Jev field confidences should not be described as calibrated probabilities without calibration evidence. A guardrail prediction alone does not establish that an entire agent deployment is safe.

## Resources

- [AgentDoG2.0 Collection](https://huggingface.co/collections/AI45Research/agentdog20-6b09556a028a2ce10c53f2fe) — public entry; model artifacts are in preparation.
- [AgentDoG 2.0 project page](https://mjc-ma-01.github.io/AgentDoG/v2_0_dark/)
- [AgentDoG source repository](https://github.com/AI45Lab/AgentDoG)
- Add the verified 2.0 technical-report URL and checkpoint-specific citation when available.
