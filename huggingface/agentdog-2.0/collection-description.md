# AgentDoG 2.0

A framework for characterizing, evaluating, and mitigating safety risks in long-horizon agent tasks, from Shanghai Artificial Intelligence Laboratory.

AgentDoG 2.0 connects a diagnostic taxonomy, long-horizon evaluation, efficient guardrails, and adaptive defenses for agents that plan, use tools, and retain state.

- **Diagnose the cause.** Organize risks across 18 risk sources, 21 failure modes, and 11 real-world harm categories.
- **Choose the guardrail for the task.** AgentDoG 2.0 produces structured trajectory judgments; AgentDoG-Jev predicts decisions and field confidences in one forward pass; AgentDoG-Step evaluates proposed actions before execution.
- **Evaluate risks that unfold over time.** ATBench-Pro targets long, stateful workflows. ManipulationArena studies covert goal manipulation across seven attack strategies, six task-native channels, and seven targeted failure modes.
- **Improve defenses from observed failures.** Harness evolution strengthens execution boundaries, while policy evolution trains safer task completion.

[Source repository](https://github.com/AI45Lab/AgentDoG)

This description summarizes the AgentDoG 2.0 technical-report manuscript. Attach only verified 2.0 artifacts to this collection; model weights, datasets, and their access conditions should be documented in each attached resource's card.

Earlier releases remain available in the separate [AgentDoG 1.5 collection](https://huggingface.co/collections/AI45Research/agentdog15) and [AgentDoG 1.0 collection](https://huggingface.co/collections/AI45Research/agentdog).
