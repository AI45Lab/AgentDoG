# AgentDoG 2.0 project page

This is a standalone, buildless page. Serve this folder with `python3 -m http.server 8765` and open `http://localhost:8765/`. No installation, server API, or model endpoint is required.

- `index.html`: bilingual section copy, experimental results, and resource links.
- `style.css`: responsive layouts, reduced-motion preferences, and accessible contrast.
- `app.js`: bilingual guardrail panels, result tabs, illustrative workflow, and figure dialog.
- `assets/`: locally hosted fonts, original brand assets, and optimized manuscript figures. Font license files are included.

The project root redirects to `v2_0/`; earlier `v1/` and `v1_5/` pages remain available. The repository root README is unchanged.

## Content provenance

Content is grounded in the supplied AgentDoG 2.0 Overleaf project. `main.tex` selects the active sources. Use `sections/guard.tex` for guard results; the separate `agentdog_jev.tex` and `agentdog_step.tex` drafts contain different older results.

| Content | Active manuscript source |
| --- | --- |
| Taxonomy: 18 risk sources, 21 failure modes, 11 harms; CGM/AOV/LoC; ATBench-Pro | `sections/safety_taxonomy.tex`, lines 11–80 |
| Base 2.0 structured guard | `sections/guard.tex`, lines 198–244 |
| Jev single-pass inference | `sections/guard.tex`, lines 473–522 |
| Jev 59.8 ms and 77.90% unsafe F1 on ATBench; binary and fine-grained latency ranges | `sections/guard.tex`, lines 664–688 |
| 109.0× Unified-4B speedup; rounded 0.060 s versus 6.52 s | `figures/jev-latency.pdf`, left panel |
| Step inference and three-benchmark results | `sections/guard.tex`, lines 694–805 |
| ManipulationArena: 7 strategies × 6 channels × 7 failure modes | `sections/agentdog_duet.tex`, lines 27–50 |
| Harness and policy evolution; one completed policy SFT round | `sections/agentdog_scenario_validation.tex`, lines 17–76 |

Step's 94.0% is mean **worst-class recall**, not accuracy. It is the unweighted mean of per-benchmark minimum safe/unsafe recall. The reported mean accuracy is 94.7%. Jev's 59.8 ms concerns **binary trajectory judgments by Unified-4B on ATBench**, not full agent runtime. Binary latency speedups and fine-grained latency speedups are separate measurements.

The risk walkthrough is a conceptual example, not a live demo or an experimental trace. Avoid promoting manuscript placeholders, preliminary counts, preview-only base-guard results, or admission thresholds in diagrams as measured gains.

## Resource updates

The supplied manuscript does not contain a public 2.0 paper URL or checkpoint IDs. Link the existing Hugging Face organization and explicitly label older releases until actual 2.0 resources are available. Do not relabel 1.5 weights as 2.0. HF collection and card drafts are in `huggingface/agentdog-2.0/`.

When the 2.0 resources are published, update the resources section in `index.html`, both languages of the release note, and the HF cards. The `og:image` URL currently uses the independent page hosted by `mjc-ma-01`; maintain it as an absolute publicly accessible URL if hosting moves.

## Validation

The page was checked in Chromium at 320, 390, 768, 1024, and 1440 px, in both languages, including all guardrail tabs. Browser checks cover result tabs, scenario stages, keyboard tab navigation, mobile navigation, image-dialog dismissal, and JavaScript errors. Local and external links were checked separately. Keep ordinary visitors independent of external font CDNs; all fonts are served locally.
