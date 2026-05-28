#!/usr/bin/env python3
import ast
import json
import re
import shutil
import time
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parents[1]
LOG_PATH = RUN_DIR / "training_current.log"
SAVE_DIR = RUN_DIR / "qwen3_5_4b_train_checkpoints"
STATE_PATH = RUN_DIR / "best_ckpt_pruner_state.json"
KEEP_LAST = int(__import__('os').environ.get('KEEP_LAST_CHECKPOINTS', '3'))
SLEEP_SECONDS = int(__import__('os').environ.get('BEST_CKPT_PRUNER_INTERVAL', '60'))

rollout_re = re.compile(r"data\.py:212 - rollout (\d+): (\{.*?\})")
ckpt_re = re.compile(r"iter_(\d+)$")

def load_state():
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}

def read_rollout_rewards():
    rewards = {}
    if not LOG_PATH.exists():
        return rewards
    text = LOG_PATH.read_text(errors='ignore')
    for m in rollout_re.finditer(text):
        try:
            step = int(m.group(1))
            data = ast.literal_eval(m.group(2))
            reward = data.get('rollout/raw_reward')
            if reward is not None:
                rewards[step] = float(reward)
        except Exception:
            continue
    return rewards

def checkpoint_step(path: Path):
    m = ckpt_re.match(path.name)
    return int(m.group(1)) if m else None

def checkpoint_complete(path: Path):
    return (path / 'metadata.json').exists() or (path / 'common.pt').exists()

def save_state(state):
    tmp = STATE_PATH.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
    tmp.replace(STATE_PATH)

def run_once():
    prev = load_state()
    prev_scores = prev.get('scores', {}) if isinstance(prev.get('scores', {}), dict) else {}
    rewards = read_rollout_rewards()
    ckpts = []
    if SAVE_DIR.exists():
        for p in SAVE_DIR.iterdir():
            if p.is_dir():
                step = checkpoint_step(p)
                if step is not None:
                    ckpts.append((step, p))
    ckpts.sort()

    # Score policy: a checkpoint's score is the raw_reward logged at its own save step.
    # Persist scores once observed so later pruning compares saved checkpoint scores.
    scores = {}
    for step, path in ckpts:
        name = path.name
        if checkpoint_complete(path) and step in rewards:
            scores[name] = float(rewards[step])
            continue
        if name in prev_scores:
            try:
                scores[name] = float(prev_scores[name])
                continue
            except Exception:
                pass

    best_name = max(scores, key=scores.get) if scores else None
    protected = {p.name for _, p in ckpts[-KEEP_LAST:]}
    if best_name:
        protected.add(best_name)
    deleted = []
    for step, path in ckpts:
        if path.name in protected:
            continue
        shutil.rmtree(path)
        deleted.append(path.name)
    state = {
        'time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'keep_last': KEEP_LAST,
        'score_policy': 'checkpoint_raw_reward_at_iter_step',
        'best_ckpt': best_name,
        'best_score': scores.get(best_name) if best_name else None,
        'protected': sorted(protected),
        'scores': {k: scores[k] for k in sorted(scores)},
        'deleted': deleted,
        'existing': [p.name for _, p in ckpts if p.exists()],
    }
    save_state(state)
    print(json.dumps(state, ensure_ascii=False), flush=True)

def main():
    while True:
        try:
            run_once()
        except Exception as exc:
            print(json.dumps({'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'error': repr(exc)}, ensure_ascii=False), flush=True)
        time.sleep(SLEEP_SECONDS)

if __name__ == '__main__':
    main()
