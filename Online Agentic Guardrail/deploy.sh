#!/bin/bash
# Deploy guardrail system to a remote OpenClaw host.
#
# Usage:
#   bash deploy.sh <ssh-target>
# Example:
#   bash deploy.sh user@my-openclaw-host
#
# Required environment variables:
#   GUARDRAIL_API_KEY    OpenAI-compatible API key for the judge model (set this outside the repository)
#   GUARDRAIL_API_BASE   (optional) API base URL, default: https://api.openai.com/v1
#   GUARDRAIL_MODEL      (optional) judge model name, default: agentdog
#   SSH_JUMP_HOST        (optional) jump host if the target is behind a bastion
#   HTTP_PROXY_URL       (optional) HTTP proxy URL if the target needs proxy for outbound

set -e

TARGET="${1:?Usage: bash deploy.sh <ssh-target>}"
GUARDRAIL_KEY="${GUARDRAIL_API_KEY:?Set GUARDRAIL_API_KEY env var with your OpenAI-compatible API key}"
API_BASE="${GUARDRAIL_API_BASE:-https://api.openai.com/v1}"
MODEL="${GUARDRAIL_MODEL:-agentdog}"
JUMP_HOST="${SSH_JUMP_HOST:-}"
PROXY_URL="${HTTP_PROXY_URL:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"

run_on_host() {
    if [ -n "$JUMP_HOST" ]; then
        ssh -CAXY "$JUMP_HOST" "ssh -CAXY '$TARGET' '$1'" 2>&1 | grep -v "post-quantum\|upgraded\|client_global"
    else
        ssh -CAXY "$TARGET" "$1" 2>&1 | grep -v "post-quantum\|upgraded\|client_global"
    fi
}

echo "=== Step 1: Update OpenClaw + disable bonjour (avoids gateway crashes) ==="
run_on_host 'zsh -i -c "npm install -g openclaw@latest 2>&1 | tail -2; openclaw --version; openclaw plugins disable bonjour 2>/dev/null || true"'

echo ""
echo "=== Step 2: Configure judge provider in OpenClaw ==="
cat > /tmp/_setup.py << PYEOF
import json
from pathlib import Path
path = Path.home() / '.openclaw/openclaw.json'
data = json.loads(path.read_text())
Path(str(path) + '.bak-pre-guardrail').write_text(path.read_text())
providers = data.setdefault('models', {}).setdefault('providers', {})
providers['judge-api'] = {
    'api': 'openai-completions',
    'baseUrl': '$API_BASE',
    'apiKey': '$GUARDRAIL_KEY',
    'models': [{'id': '$MODEL', 'name': '$MODEL', 'reasoning': False,
                'input': ['text'], 'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0},
                'contextWindow': 128000, 'maxTokens': 8192}],
}
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
print('CONFIG OK: judge-api/$MODEL added')
PYEOF
B64=$(base64 < /tmp/_setup.py)
run_on_host "echo $B64 | base64 -d | python3"

echo ""
echo "=== Step 3: Deploy guardrail Python module ==="
cd "$PROJECT_DIR"
tar czf /tmp/_guardrail.tar.gz \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='tests' --exclude='hook' --exclude='plugin' \
    guardrail/__init__.py guardrail/__main__.py guardrail/cli.py \
    guardrail/config.py guardrail/evaluator.py guardrail/prompt.py \
    guardrail/runner.py guardrail/server.py guardrail/trajectory.py \
    guardrail/watcher.py guardrail/guardrail.json guardrail/dashboard.html \
    guardrail/inspections.html guardrail/assets \
    guardrail/proxy.py guardrail/ws_proxy.py
B64=$(base64 < /tmp/_guardrail.tar.gz)
run_on_host "echo $B64 | base64 -d > /tmp/_g.tar.gz && cd \$HOME && tar xzf /tmp/_g.tar.gz && echo GUARDRAIL_DEPLOYED"

echo ""
echo "=== Step 3b: Install guardrail runtime dependencies ==="
run_on_host 'python3 -m venv $HOME/.agentdog-guardrail-venv && $HOME/.agentdog-guardrail-venv/bin/python -m pip install -U pip && $HOME/.agentdog-guardrail-venv/bin/python -m pip install "websockets>=12"'

echo ""
echo "=== Step 4: Deploy OpenClaw plugin ==="
B64_INDEX=$(base64 < "$SCRIPT_DIR/plugin/index.js")
B64_MANIFEST=$(base64 < "$SCRIPT_DIR/plugin/openclaw.plugin.json")
cat > /tmp/_deploy_plugin.sh << 'PLUGEOF'
#!/bin/zsh
source ~/.zshrc 2>/dev/null
OPENCLAW_DIR=$(dirname $(dirname $(readlink -f $(which openclaw))))/lib/node_modules/openclaw
EXTDIR=$OPENCLAW_DIR/dist/extensions/guardrail-pre-reply
mkdir -p $EXTDIR
echo "$PLUGIN_INDEX_B64" | base64 -d > $EXTDIR/index.js
echo "$PLUGIN_MANIFEST_B64" | base64 -d > $EXTDIR/openclaw.plugin.json
ENTRY=$(ls $OPENCLAW_DIR/dist/plugin-entry-*.js 2>/dev/null | head -1 | xargs basename)
if [ -n "$ENTRY" ]; then
    sed -i "s/plugin-entry-[A-Za-z0-9_-]*\.js/$ENTRY/" $EXTDIR/index.js
fi
echo "PLUGIN_DEPLOYED to $EXTDIR (entry: $ENTRY)"
PLUGEOF
B64_SCRIPT=$(base64 < /tmp/_deploy_plugin.sh)
if [ -n "$JUMP_HOST" ]; then
    ssh -CAXY "$JUMP_HOST" "ssh -CAXY '$TARGET' 'export PLUGIN_INDEX_B64=\"$B64_INDEX\" && export PLUGIN_MANIFEST_B64=\"$B64_MANIFEST\" && echo $B64_SCRIPT | base64 -d | zsh'" 2>&1 | grep -v "post-quantum\|upgraded\|client_global\|---"
else
    ssh -CAXY "$TARGET" "export PLUGIN_INDEX_B64=\"$B64_INDEX\" && export PLUGIN_MANIFEST_B64=\"$B64_MANIFEST\" && echo $B64_SCRIPT | base64 -d | zsh" 2>&1 | grep -v "post-quantum\|upgraded\|client_global\|---"
fi

echo ""
echo "=== Step 5: Read gateway token ==="
TOKEN_CMD='python3 -c "import json; from pathlib import Path; print(json.loads((Path.home()/\".openclaw/openclaw.json\").read_text())[\"gateway\"][\"auth\"][\"token\"])"'
if [ -n "$JUMP_HOST" ]; then
    TOKEN=$(ssh -CAXY "$JUMP_HOST" "ssh -CAXY '$TARGET' '$TOKEN_CMD'" 2>&1 | grep -v "post-quantum\|upgraded\|client_global\|WARNING" | tr -d '[:space:]')
else
    TOKEN=$(ssh -CAXY "$TARGET" "$TOKEN_CMD" 2>&1 | grep -v "post-quantum\|upgraded\|client_global\|WARNING" | tr -d '[:space:]')
fi
echo "Gateway token: ${TOKEN:0:10}..."

echo ""
echo "============================================"
echo "  DEPLOYMENT COMPLETE"
echo "============================================"
echo ""
echo "On the host, open 4 terminals and run:"
echo ""
echo "Terminal 1 — Gateway:"
echo "  openclaw gateway"
echo ""
echo "Terminal 2 — Guardrail Service:"
echo "  cd ~"
echo "  GUARDRAIL_PY=\$HOME/.agentdog-guardrail-venv/bin/python"
echo "  export GUARDRAIL_API_KEY=\$YOUR_JUDGE_API_KEY"
if [ -n "$PROXY_URL" ]; then
echo "  export http_proxy=$PROXY_URL"
echo "  export https_proxy=$PROXY_URL"
echo "  export no_proxy=127.0.0.1,localhost"
fi
echo "  \$GUARDRAIL_PY -m guardrail serve --port 8340"
echo ""
echo "Terminal 3 — WS Proxy:"
echo "  cd ~"
echo "  GUARDRAIL_PY=\$HOME/.agentdog-guardrail-venv/bin/python"
echo "  \$GUARDRAIL_PY -m guardrail ws-proxy --port 18790 --guardrail-url http://127.0.0.1:8340"
echo ""
echo "Terminal 4 — TUI (via proxy):"
echo "  openclaw tui --url ws://127.0.0.1:18790 --token $TOKEN"
echo ""
echo "Dashboard (your local machine):"
if [ -n "$JUMP_HOST" ]; then
echo "  ssh -L 8340:127.0.0.1:8340 -CAXY $JUMP_HOST -t \"ssh -L 8340:127.0.0.1:8340 -CAXY $TARGET\""
else
echo "  ssh -L 8340:127.0.0.1:8340 -CAXY $TARGET"
fi
echo "  Then open: http://localhost:8340/"
