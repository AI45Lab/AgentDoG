# AgentDog Guardrail Design

## Overview

AgentDog Guardrail is an online PRE_REPLY guardrail for OpenClaw-style agents.
It separates agent execution from reply delivery: the agent may complete its
normal tool-augmented turn, but the final reply draft is held until a guardrail
judge reviews the full trajectory. AgentDog is the default judge model.

This open-source copy contains framework code only. It does not include private
session replays, benchmark traces, generated figures, or credentials.

## Architecture

```text
OpenClaw TUI
    │
    │ websocket
    ▼
Guardrail WS Proxy
    │  buffers run events until final reply
    │
    ├── if safe: flush original events to the user
    └── if unsafe: suppress original reply and emit replacement message

Guardrail HTTP Service
    ├── POST /evaluate       trajectory-level verdict
    ├── POST /check          session_events JSONL verdict
    ├── GET  /dashboard/*    live session monitoring
    └── GET  /dashboard/events

Judge Model
    └── OpenAI-compatible chat completions endpoint
```

## Main Modules

- `guardrail/ws_proxy.py`: WebSocket proxy that performs PRE_REPLY buffering and
  delivery control.
- `guardrail/server.py`: HTTP API, dashboard asset serving, SSE event streaming,
  and cached verdict support.
- `guardrail/evaluator.py`: Judge-model client. It sends a formatted trajectory
  and parses a JSON verdict.
- `guardrail/trajectory.py`: Parser for OpenClaw `session_events.jsonl` files.
- `guardrail/watcher.py`: Polling watcher for live dashboard sessions.
- `guardrail/dashboard.html`: Live monitoring dashboard. No replay data is
  embedded in the open-source build.
- `guardrail/inspections.html`: Live inspection view. No curated case data is
  embedded in the open-source build.

## PRE_REPLY Flow

1. The TUI sends a user request through the WebSocket proxy.
2. The proxy forwards it to the OpenClaw Gateway.
3. The agent runs normally and may call tools.
4. The proxy buffers streaming events instead of immediately forwarding the final
   user-visible reply.
5. When the final reply state arrives, the proxy formats the trajectory and
   calls the guardrail service.
6. Safe verdicts release the original reply.
7. Unsafe verdicts suppress the original reply and send a replacement message.

## Data Handling

The framework inspects local OpenClaw session files from
`~/.openclaw/agents/*/sessions` by default. `--sessions-dir` can override this
with one directory, a glob, or a comma-separated list. Session files are runtime
data and should not be committed. Keep replay and verdict-cache directories
outside the source bundle.

## Configuration

The config file supports `$ENV_VAR` substitution for string fields:

```json
{
  "enabled": true,
  "api_base": "$GUARDRAIL_API_BASE",
  "model": "$GUARDRAIL_MODEL",
  "api_key": "$GUARDRAIL_API_KEY",
  "timeout_seconds": 60
}
```

If `GUARDRAIL_MODEL` is not set, the config loader defaults to `agentdog`.

If the guardrail service or judge model fails, the runtime returns an error
verdict with `prediction=-1`. The current proxy treats guardrail failures as
non-blocking to avoid interrupting availability.
