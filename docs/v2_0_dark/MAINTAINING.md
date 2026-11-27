# AgentDoG 2.0 — dark edition

This edition follows the original AgentDoG 1.5 visual system: nearly black surfaces, cyan/violet gradients, a centered brand hero, glass navigation, and research figures presented inline. The previous light edition remains at `docs/v2_0/`.

The page is buildless. Serve `docs/` using `python3 -m http.server 8775 --directory docs` from the repository root, then open `http://localhost:8775/v2_0_dark/`.

## Files

- `index.html`: bilingual research narrative, four comparison/result tables, and inline figures.
- `style.css`: independent dark theme and responsive layouts; does not alter shared 1.x styles.
- `examples.js`: three explicitly conceptual CGM/AOV/LoC examples, each with four stages, a diagnosis, and a safe continuation.
- `app.js`: language selection, model-table filters, case playback, accessible navigation, and figure expansion with actual-size viewing.
- `assets/`: eight faithfully converted manuscript figures, the original logo, local fonts with licenses, and the dark social preview.

The root README and the light edition are unchanged by this edition. Dedicated 2.0 checkpoint and paper URLs remain pending; resource links describe the existing published ecosystem accurately. Hugging Face release drafts are retained at `huggingface/agentdog-2.0/`.

## Content and provenance

Use the active sources selected by the supplied Overleaf `main.tex`. Main results are in `sections/guard.tex`, not the older standalone Jev/Step section drafts. Further provenance is recorded in `docs/v2_0/MAINTAINING.md` and this edition's `assets/manifest.json`.

Key scopes to preserve when editing:

- Jev Unified-4B: **59.8 ms / 77.90% unsafe F1 on ATBench**; Jev Qwen3.5-4B: **58.9 ms / 87.64% unsafe F1 on R-Judge**.
- Jev binary-decision speedups: **103.9–184.9×** versus corresponding 1.5 checkpoints; fine-grained diagnosis: **4.4–13.4×**, with a separate speed/accuracy trade-off.
- The **109.0×** Unified-4B latency comparison comes from the manuscript figure, which rounds 59.8 ms to 0.060 s and uses a 6.52 s baseline.
- Step 4B: **94.7% mean accuracy, 87.5% mean unsafe F1, 94.0% mean worst-class recall**, unweighted across TS-Bench-Dojo, TS-Bench-ASB, and StepShield. Worst-class recall is the minimum of safe/unsafe recall per benchmark, averaged afterwards.
- Current taxonomy: **18 risk sources / 21 failure modes / 11 harms**. Avoid a numerical comparison to the 1.5 taxonomy, since older webpage and manuscript counts disagree.
- ManipulationArena: **7 strategies × 6 channels × 7 failure modes = 294 configurations**; instance counts remain unresolved in the manuscript.
- Harness diagram thresholds are validation criteria, not measured gains. The policy evolution figure reports **one completed SFT round**, with further multi-round improvements still to be evaluated.

All walkthroughs are explanations, not live inference or measured experimental traces. Playback highlights their stages; it does not call an API or model.
