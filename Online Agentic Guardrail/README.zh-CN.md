# AgentDog Guardrail

这是一个面向 OpenClaw Agent 的开源 PRE_REPLY 安全护栏。它作为独立服务运行在
OpenClaw 旁边，可以记录本地 session 文件，并通过 WebSocket proxy 在最终回复发
送给用户之前完成截流审查。

这个仓库只保留框架和功能代码，不包含私有 replay session、benchmark trace、生
成图、缓存 verdict、API key 或临时 demo case。

英文文档：[README.md](README.md)

## 功能

- 默认使用 AgentDog 作为 trajectory judge model。
- 默认从 `~/.openclaw/agents/*/sessions` 发现所有 OpenClaw agent session。
- 将发现到的 OpenClaw session 记录并实时流式展示到 dashboard。
- 在 PRE_REPLY 阶段代理 OpenClaw Gateway WebSocket 流量。
- 暂存 Agent 的最终回复草稿，交给 AgentDog 审核，再决定放行或替换。
- 提供本地 dashboard 和 inspection 页面，不内置示例 replay 数据。

## 目录结构

```text
Online Agentic Guardrail/
├── guardrail/
│   ├── ws_proxy.py          # PRE_REPLY WebSocket 截流
│   ├── server.py            # HTTP API、SSE、前端静态资源
│   ├── evaluator.py         # OpenAI-compatible judge model client
│   ├── trajectory.py        # OpenClaw session_events 解析
│   ├── watcher.py           # OpenClaw session 发现与文件轮询
│   ├── dashboard.html       # 实时监控页面，不包含 replay 数据
│   ├── inspections.html     # 实时 inspection 页面，不包含 replay 数据
│   └── guardrail.json       # 基于环境变量的配置模板
├── plugin/                  # OpenClaw plugin companion
├── hook/                    # 旧版 hook 示例
├── deploy.sh                # 可选远程部署脚本
├── README.md                # 英文文档
└── pyproject.toml
```

## 依赖

- Python 3.10+
- 本地已经安装并配置好的 OpenClaw
- 一个 OpenAI-compatible endpoint，用来服务 `agentdog` judge model

创建虚拟环境并安装 Python 依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

## 配置 AgentDog

通过环境变量配置 judge endpoint。不要把真实凭证提交到仓库。

```bash
export GUARDRAIL_API_BASE="https://your-agentdog-endpoint.example/v1"
export GUARDRAIL_MODEL="agentdog"
export GUARDRAIL_API_KEY="$YOUR_JUDGE_API_KEY"
```

仓库内置的 `guardrail/guardrail.json` 会读取这些环境变量。如果没有设置
`GUARDRAIL_MODEL`，Python 配置默认使用 `agentdog`。

```json
{
  "enabled": true,
  "api_base": "$GUARDRAIL_API_BASE",
  "model": "$GUARDRAIL_MODEL",
  "api_key": "$GUARDRAIL_API_KEY",
  "timeout_seconds": 60
}
```

## 和 OpenClaw 一起运行

终端 1：启动 OpenClaw Gateway。

```bash
openclaw gateway
```

终端 2：启动 guardrail service。不传 `--sessions-dir` 时，它会默认监听所有匹配
`~/.openclaw/agents/*/sessions` 的 OpenClaw agent session 目录。

```bash
python -m guardrail serve --host 127.0.0.1 --port 8340
```

如果要覆盖监听范围，可以传单个目录、glob，或逗号分隔的多目录：

```bash
python -m guardrail serve \
  --port 8340 \
  --sessions-dir "~/.openclaw/agents/main/sessions,~/.openclaw/agents/worker/sessions"
```

终端 3：启动 PRE_REPLY WebSocket proxy。

```bash
python -m guardrail ws-proxy \
  --port 18790 \
  --gateway ws://127.0.0.1:18789 \
  --guardrail-url http://127.0.0.1:8340
```

终端 4：让 OpenClaw TUI 通过 proxy 连接。

```bash
openclaw tui --url ws://127.0.0.1:18790 --token "$OPENCLAW_GATEWAY_TOKEN"
```

打开页面：

```text
http://127.0.0.1:8340/
http://127.0.0.1:8340/inspections.html
```

## 运行时行为

1. 用户通过被代理的 OpenClaw TUI 发送消息。
2. proxy 将请求转发给 OpenClaw Gateway。
3. Agent 正常执行，可以调用工具。
4. proxy 缓冲这一轮 Agent 输出，直到最终回复草稿出现。
5. AgentDog 在 PRE_REPLY 阶段审查完整 trajectory。
6. 如果判定安全，原回复照常送达。
7. 如果判定不安全，原回复被抑制，并替换为 guardrail 警示回复。

Dashboard 也会读取 OpenClaw 的 `session_events.jsonl` 文件，并在文件增长时实时
展示新增事件。

## 数据策略

这个开源版本有意排除了：

- `converted_sessions/`
- `converted_dashboard_sessions/`
- 生成图和演示文稿产物
- `.guardrail.json` 与 `.guardrail-history.jsonl` verdict cache
- 私有 API key、凭证、benchmark payload 和 replay 示例

私有 trace 应保留在仓库之外。可以通过 `--sessions-dir` 或
`OPENCLAW_SESSIONS_DIRS` 指向本地运行时数据。
