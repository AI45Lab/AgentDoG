# Runtime API and Schema Notes

## Runtime Catalog

`data/runtime_catalog.json` is a JSON object with a `runtime_catalog` mapping from `task_id` to runtime task bundles. Each bundle contains:

- `task_spec`: user query, domain metadata, selected tools, scenario labels, success/risk specs.
- `tool_registry_view`: agent-facing tool schemas.
- `execution_bundle`: initial state template, scenarios, tool implementation sources.
- `server_adapter_manifest`: tool dispatch table.
- `evaluation_bundle`: final-state/domain-outcome success rules.

## Pairing File

`data/semantic_local_pairing.jsonl` is JSONL. Each line has:

- `family_key`: local semantic family id.
- `base_family_key`: original semantic family id.
- `clean.task_id`: required clean anchor task.
- `attacks[].task_id`: zero or more environment-injection attacked variants.
- `queries[].task_id`: zero or more query_target variants.

The grouped sampler expands each line into a local sequence. The default order is clean, then attacks, then query_target variants when present.

## Task Types

- `clean`: benign utility task.
- `attack`: environment-injection attacked task.
- `query_target`: malicious-query / query-target task. It may use the clean scenario but is identified by task type metadata.

## Episode Lifecycle

1. Sample or choose a task id.
2. Start an episode with `/episodes/start`.
3. Execute one or more tool calls with `/episodes/{episode_id}/tool-call`.
4. Finish the episode with `/episodes/{episode_id}/finish`.
5. The server releases the episode executor on finish/delete/TTL expiry.
