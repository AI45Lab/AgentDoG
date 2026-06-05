# AgentDog Guardrail

Open-source PRE_REPLY safety guardrail for OpenClaw agents. The service runs
alongside OpenClaw, records local session files, and intercepts final replies
through a WebSocket proxy before they are delivered to the user.

This repository contains the framework only. It does not bundle private replay
sessions, benchmark traces, generated figures, cached verdicts, API keys, or
temporary example cases.

Chinese documentation: [README.zh-CN.md](README.zh-CN.md)

## What It Does

- Uses AgentDog as the default trajectory judge model.
- Discovers OpenClaw sessions from `~/.openclaw/agents/*/sessions` by default.
- Records and streams every discovered OpenClaw session into the dashboard.
- Proxies OpenClaw Gateway WebSocket traffic at PRE_REPLY time.
- Holds the final reply draft, sends the trajectory to AgentDog, then releases
  or replaces the reply.
- Serves a local dashboard and inspection page without bundled example replays.

## Repository Layout

```text
Online Agentic Guardrail/
├── guardrail/
│   ├── ws_proxy.py          # PRE_REPLY WebSocket interception
│   ├── server.py            # HTTP API, SSE, dashboard assets
│   ├── evaluator.py         # OpenAI-compatible judge-model client
│   ├── trajectory.py        # OpenClaw session_events parser
│   ├── watcher.py           # OpenClaw session discovery and file polling
│   ├── dashboard.html       # Live monitoring UI, no bundled replay data
│   ├── inspections.html     # Live inspection UI, no bundled replay data
│   └── guardrail.json       # Env-var based config template
├── plugin/                  # OpenClaw plugin companion
├── hook/                    # Legacy hook example
├── deploy.sh                # Optional remote deploy helper
├── README.zh-CN.md          # Chinese documentation
└── pyproject.toml
```

## Requirements

- Python 3.10+
- OpenClaw installed and configured locally
- An OpenAI-compatible endpoint that serves the `agentdog` judge model

Create a virtual environment and install Python dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

## Configure AgentDog

Set the judge endpoint through environment variables. Do not commit real
credentials.

```bash
export GUARDRAIL_API_BASE="https://your-agentdog-endpoint.example/v1"
export GUARDRAIL_MODEL="agentdog"
export GUARDRAIL_API_KEY="$YOUR_JUDGE_API_KEY"
```

The bundled `guardrail/guardrail.json` references those variables. If
`GUARDRAIL_MODEL` is not set, the Python config defaults to `agentdog`.

```json
{
  "enabled": true,
  "api_base": "$GUARDRAIL_API_BASE",
  "model": "$GUARDRAIL_MODEL",
  "api_key": "$GUARDRAIL_API_KEY",
  "timeout_seconds": 60
}
```

## Run With OpenClaw

Terminal 1: start OpenClaw Gateway.

```bash
openclaw gateway
```

Terminal 2: start the guardrail service. Without `--sessions-dir`, it watches
all OpenClaw agent session directories matching `~/.openclaw/agents/*/sessions`.

```bash
python -m guardrail serve --host 127.0.0.1 --port 8340
```

To override the watched sessions, pass a directory, glob, or comma-separated
list:

```bash
python -m guardrail serve \
  --port 8340 \
  --sessions-dir "~/.openclaw/agents/main/sessions,~/.openclaw/agents/worker/sessions"
```

Terminal 3: start the PRE_REPLY WebSocket proxy.

```bash
python -m guardrail ws-proxy \
  --port 18790 \
  --gateway ws://127.0.0.1:18789 \
  --guardrail-url http://127.0.0.1:8340
```

Terminal 4: connect OpenClaw TUI through the proxy.

```bash
openclaw tui --url ws://127.0.0.1:18790 --token "$OPENCLAW_GATEWAY_TOKEN"
```

Open the UIs:

```text
http://127.0.0.1:8340/
http://127.0.0.1:8340/inspections.html
```

## Runtime Behavior

1. The user sends a message through the proxied OpenClaw TUI.
2. The proxy forwards the request to OpenClaw Gateway.
3. The agent runs normally and may call tools.
4. The proxy buffers the agent turn until the final reply draft arrives.
5. AgentDog judges the full trajectory at PRE_REPLY.
6. Safe verdict: the original reply is delivered.
7. Unsafe verdict: the original reply is suppressed and replaced by a guardrail
   warning.

The dashboard also reads OpenClaw `session_events.jsonl` files and streams new
events as the files grow.

## Data Policy

This open-source copy intentionally excludes:

- `converted_sessions/`
- `converted_dashboard_sessions/`
- generated figures and presentation artifacts
- `.guardrail.json` and `.guardrail-history.jsonl` verdict caches
- private API keys, credentials, benchmark payloads, and replay examples

Keep private traces outside the repository. Use `--sessions-dir` or
`OPENCLAW_SESSIONS_DIRS` to point the service at local runtime data.
