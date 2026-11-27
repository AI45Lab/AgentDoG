# Publishing AgentDoG 2.0 on Hugging Face

The public [AgentDoG2.0 Collection](https://huggingface.co/collections/AI45Research/agentdog20-6b09556a028a2ce10c53f2fe) was created under `AI45Research` on 2026-11-27. The entry intentionally has no items while the 2.0 models and datasets are in preparation. Model and dataset cards in this directory remain local release drafts. The repository's root README is outside this change.

## What is ready

- `collection-description.md`: the published short plain-text description and an optional longer introduction for external documentation.
- `model-card-template.md`: YAML-front-matter template for a specific guard, Jev, or Step checkpoint.
- `dataset-card-template.md`: YAML-front-matter template for a specific ATBench-Pro or ManipulationArena release.

The live [AgentDoG 2.0 project page](https://mjc-ma-01.github.io/AgentDoG/v2_0_dark/) uses the dark visual style of the original project. The manuscript provides no verified 2.0 arXiv URL or model/dataset repository IDs.

The Collection slug is `AI45Research/agentdog20-6b09556a028a2ce10c53f2fe`. Reuse this entry when adding ready artifacts. HF Collections accept a plain-text description of at most 150 characters; the current description is 142 characters. The longer Markdown introduction in `collection-description.md` is for external documentation rather than the Collection description field.

## Required before publishing model or dataset artifacts

1. **Hugging Face authentication:** sign in to the intended HF account with permission to write to the destination namespace. A GitHub personal access token does not provide Hugging Face access. Use HF's normal login or a suitably scoped HF token; keep credentials outside cards, source files, and Git history.
2. **Confirmed destination:** the Collection is public under `AI45Research`. Confirm the exact model and dataset repository IDs and their visibility before uploading; do not invent 2.0 artifact IDs.
3. **Actual release artifacts:** identify the exact weights, tokenizer/configuration, base-model revision, and supported loader for each checkpoint; identify the actual dataset files, schemas, splits, annotations, and evaluation code. The Overleaf archive is a manuscript source, not a checkpoint or dataset release package.
4. **Release metadata:** confirm each resource's license, access conditions, intended use, limitations, citation, and any required base-model attribution. Complete the relevant template and save it as `README.md` in that HF resource's checkout.

Publish each completed card with its corresponding files, then add verified 2.0 resources to the existing Collection. Review rendered cards and test a real download/loading path before describing an attached model or dataset as available. The public Collection itself can already serve as the project's HF entry point.

## Claims that need care

- The active manuscript reports 18 risk sources, 21 failure modes, and 11 real-world harms. The existing 1.5 webpage has inconsistent historical category counts; use the 2.0 manuscript for new content.
- Jev's reported **59.8 ms** is the mean trajectory-level latency of **Jev Unified-4B on ATBench**, paired with **77.9% unsafe F1**. It is not a universal latency for all tasks or checkpoints.
- The reported **103.9–184.9×** lower mean latency applies to binary decisions against corresponding generative AgentDoG 1.5 checkpoints. Fine-grained diagnosis has a different speed/accuracy trade-off.
- Step 4B's **94.0% mean worst-class recall** is the unweighted average across TS-Bench-Dojo, TS-Bench-ASB, and StepShield. It is not 94% accuracy or a deployment safety guarantee.
- Do not publish unfinished base-guard result cells, ATBench-Pro dataset sizes, or provisional manipulation-benchmark counts. The source has unresolved values.
- The manuscript reports one completed policy SFT round; do not claim measured multi-round policy evolution or unchanged task utility.

Source anchors in the supplied Overleaf project: `main.tex:272–283` selects the active sections; taxonomy and benchmarks are in `sections/safety_taxonomy.tex`; guard/Jev/Step methods and results are in `sections/guard.tex`; ManipulationArena is in `sections/agentdog_duet.tex`; evolution scope is in `sections/agentdog_scenario_validation.tex`. Use active included sections rather than older standalone section drafts.

## Earlier resources remain separate

The AgentDoG2.0 Collection is public; dedicated 2.0 model and dataset artifacts remain in preparation. Earlier 1.0 and 1.5 resources remain in their own collections. Recheck artifact availability before adding download links, including private resources visible to the authenticated account.

- [AgentDoG 1.5 collection](https://huggingface.co/collections/AI45Research/agentdog15)
- [AgentDoG 1.0 collection](https://huggingface.co/collections/AI45Research/agentdog)
- [ATBench](https://huggingface.co/datasets/AI45Research/ATBench)
- [ATBench-Claw](https://huggingface.co/datasets/AI45Research/ATBench-Claw)
- [ATBench-Codex](https://huggingface.co/datasets/AI45Research/ATBench-Codex)

Do not rename existing 1.x weights or relabel their results as 2.0. A new collection can link prior benchmarks if their existing names and versions remain explicit.
