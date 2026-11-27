---
tags:
  - agent-safety
  - long-horizon
  - safety-evaluation
  - agentdog
---

<!-- TEMPLATE: Complete dataset-specific fields before publishing this as a dataset repository README.md. Do not publish the selection instructions below. -->

# DATASET NAME — AgentDoG 2.0

## Dataset description

This dataset supports the evaluation of safety risks in long-horizon agent workflows studied by AgentDoG 2.0, from Shanghai Artificial Intelligence Laboratory.

**Dataset role:** REPLACE WITH ONE VERIFIED DESCRIPTION:

- **ATBench-Pro:** trajectory-level evaluation for long, stateful workflows involving delayed triggers, changing authority, and accumulating errors.
- **ManipulationArena:** an execution-grounded benchmark for covert goal manipulation, composing seven attack strategies, six task-native channels, and seven targeted failure modes.

## Data structure

Document the actual downloadable files, configurations, splits, split sizes, languages, field names, label vocabulary, and one sanitized record. For trajectories, explain action/observation ordering and how persistent state is represented. For attack records, explain the carrier, intervention timing, target behavior, and execution-grounded success criterion when provided.

## Collection and annotation

Describe the source environments, generation or collection procedure, annotation protocol, adjudication, filtering, deduplication, and split construction. State which labels are human adjudicated and which are automated. Include provenance and redistribution rights for third-party material.

## Evaluation and limitations

Provide the released evaluation command, required model or environment dependencies, metric definitions, and any contamination controls. Distinguish trajectory-level diagnosis from action-level interception. Explain which threat scenarios and environments are covered and which remain outside the dataset's scope.

## Data governance

Complete the dataset license, access conditions, sensitive-content notice, privacy review, redaction procedure, and contact or issue-reporting channel. Agent-safety data can contain harmful instructions or simulated unsafe actions; its inclusion supports evaluation rather than endorsement.

## Resources

- [AgentDoG2.0 Collection](https://huggingface.co/collections/AI45Research/agentdog20-6b09556a028a2ce10c53f2fe) — public entry; dataset artifacts are in preparation.
- [AgentDoG 2.0 project page](https://mjc-ma-01.github.io/AgentDoG/v2_0_dark/)
- [AgentDoG source repository](https://github.com/AI45Lab/AgentDoG)
- Add the verified 2.0 technical-report URL and dataset-specific citation when available.
