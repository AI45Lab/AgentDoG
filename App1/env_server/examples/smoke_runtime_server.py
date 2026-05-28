#!/usr/bin/env python3
import argparse
import json
import urllib.request


def post(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get(url):
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:18080")
    ap.add_argument("--seed", type=int, default=20260521)
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    health = get(base + "/health")
    print("health", json.dumps(health, ensure_ascii=False))
    reinit = post(base + "/admin/reinit-sampler", {"seed": args.seed})
    print("reinit", json.dumps(reinit, ensure_ascii=False))
    sample = post(base + "/tasks/sample", {})
    print("sample", json.dumps({k: sample.get(k) for k in ["task_id", "task_type", "scenario", "family_key"]}, ensure_ascii=False))
    ep = post(base + "/episodes/start", {"task_id": sample["task_id"], "scenario": sample.get("scenario") or "clean"})
    print("episode", json.dumps({"episode_id": ep.get("episode_id"), "tools": len(ep.get("available_tools") or [])}, ensure_ascii=False))
    finish = post(base + f"/episodes/{ep['episode_id']}/finish", {"final_answer": "smoke test", "finish_reason": "smoke"})
    print("finish", json.dumps({"ok": finish.get("ok"), "evaluation_keys": sorted((finish.get("evaluation") or {}).keys())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
