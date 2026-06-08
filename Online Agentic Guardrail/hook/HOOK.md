---
name: guardrail-pre-reply
description: "PRE_REPLY safety guardrail — evaluates agent trajectory via AgentDog before reply is sent. Blocks unsafe replies."
metadata:
  { "openclaw": {
    "emoji": "🛡️",
    "events": ["message_sending"],
    "requires": { "bins": ["node"] },
    "export": "default"
  } }
---

# Guardrail PRE_REPLY Hook

Evaluates the agent's full execution trajectory before each reply is sent to the user.
Uses AgentDog to judge whether the trajectory contains unsafe actions or decision patterns.

- **safe** (pred=0): reply is sent normally
- **unsafe** (pred=1): reply is cancelled, user is notified
- **error**: fail-open, reply is sent (guardrail failure must not block normal operation)

## Configuration

Set `GUARDRAIL_API_KEY` environment variable before starting the gateway.
Edit `config.json` in this directory for API endpoint and model settings.
