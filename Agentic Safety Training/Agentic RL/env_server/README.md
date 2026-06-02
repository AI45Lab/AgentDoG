# Lightweight Agent Environment Runtime Release

This directory is a runtime-only release package for serving synthesized lightweight agent environments. It intentionally excludes the LLM synthesis pipeline and prompt-generation code. The package contains the environment server, runtime schema/evaluator code, the released runtime catalog, semantic pairing metadata, and smoke/profiling scripts.

## Contents

```text
server.py                         # entry point
tasksvc/runtime/                  # env server, episode lifecycle, tool execution bridge
tasksvc/assembly/                 # runtime catalog loader and bundle validation
tasksvc/rules/                    # final-state/risk success evaluators
tasksvc/common/                   # shared runtime contracts
data/runtime_catalog.json         # released runtime catalog, 15,774 tasks
data/task_drafts.json             # source task drafts metadata, optional for serving
data/semantic_local_pairing.jsonl # clean/attack/query_target local grouping
scripts/                          # scalability/stress profiling scripts
examples/smoke_runtime_server.py  # minimal client smoke test
```

## Dataset Summary

The bundled release catalog contains 15,774 runtime tasks:

- clean: 3,552
- environment-injection attack: 9,994
- query_target: 2,228

The semantic pairing file contains 9,715 local groups. Groups are served in clean -> attack -> query_target order when variants exist, while group order is shuffled by seed.

## Start Server

```bash
python3 server.py   --host 0.0.0.0   --port 18080   --backend placeholder   --catalog-file data/runtime_catalog.json   --tool-exec-timeout 30   --episode-ttl-seconds 7200   --max-episodes 2048   --episode-max-steps 30   --sampling-mode grouped_triplet   --pairing-file data/semantic_local_pairing.jsonl   --group-variant-policy one_each   --group-shuffle-seed 20260521
```

## API

- `GET /health`: server status, task count, active episode count.
- `GET /catalog/tasks`: public task metadata.
- `POST /tasks/sample`: sample the next task. In grouped mode this follows the semantic local-pairing queue.
- `POST /admin/reinit-sampler`: reset grouped sampler order with a seed, e.g. `{ "seed": 20260521 }`.
- `POST /episodes/start`: body `{ "task_id": "...", "scenario": "clean|attacked" }`.
- `POST /episodes/{episode_id}/tool-call`: body `{ "tool_name": "...", "arguments": {...} }`.
- `POST /episodes/{episode_id}/finish`: body `{ "final_answer": "...", "finish_reason": "done" }`.
- `DELETE /episodes/{episode_id}`: release episode state.

## Smoke Test

```bash
python3 examples/smoke_runtime_server.py --base-url http://127.0.0.1:18080
```

## Notes

- The server consumes prebuilt runtime catalogs. LLM task synthesis is not included in this release package.
- Reward/evaluation is final-state/domain-outcome based. Tool self-reported success is not the primary success criterion.
- The included `task_drafts.json` is not required to serve environments; it is retained for metadata inspection.
