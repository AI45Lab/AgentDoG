import argparse
import json
import random
import statistics
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def _request_json(method, url, payload=None, timeout=30):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            elapsed = time.time() - started
            parsed = json.loads(body) if body else {}
            return resp.status, parsed, elapsed
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        elapsed = time.time() - started
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"ok": False, "raw_body": body}
        return exc.code, parsed, elapsed


def _build_minimal_arguments(tool_schema):
    function = (tool_schema or {}).get("function") or {}
    parameters = (function.get("parameters") or {}).get("properties") or {}
    required = (function.get("parameters") or {}).get("required") or []
    args = {}
    for key in required:
        spec = parameters.get(key) or {}
        arg_type = spec.get("type")
        lowered = str(key).lower()
        if arg_type == "integer":
            args[key] = 1
        elif arg_type == "number":
            args[key] = 1.0
        elif arg_type == "boolean":
            args[key] = True
        elif "date" in lowered:
            args[key] = "2026-04-16"
        elif "time" in lowered:
            args[key] = "09:00"
        elif "url" in lowered:
            args[key] = "https://example.com"
        elif lowered.endswith("_id") or lowered == "id":
            args[key] = "sample_001"
        else:
            args[key] = "sample_value"
    return args


def _run_episode(base_url, task_id):
    record = {
        "task_id": task_id,
        "start_ok": False,
        "tool_ok": False,
        "finish_ok": False,
        "start_status": None,
        "tool_status": None,
        "finish_status": None,
        "start_latency": None,
        "tool_latency": None,
        "finish_latency": None,
        "error_type": None,
    }

    status, start_data, latency = _request_json(
        "POST",
        f"{base_url}/episodes/start",
        {"task_id": task_id},
    )
    record["start_status"] = status
    record["start_latency"] = latency
    if status != 200 or not start_data.get("ok"):
        record["error_type"] = start_data.get("error") or "episode_start_failed"
        return record
    record["start_ok"] = True

    episode_id = start_data.get("episode_id")
    tools = start_data.get("available_tools") or []
    if not tools:
        record["error_type"] = "no_available_tools"
        return record

    tool_schema = tools[0]
    tool_name = ((tool_schema or {}).get("function") or {}).get("name")
    arguments = _build_minimal_arguments(tool_schema)
    status, tool_data, latency = _request_json(
        "POST",
        f"{base_url}/episodes/{episode_id}/tool-call",
        {"tool_name": tool_name, "arguments": arguments},
    )
    record["tool_status"] = status
    record["tool_latency"] = latency
    if status == 200 and tool_data.get("ok"):
        record["tool_ok"] = True
    else:
        record["error_type"] = tool_data.get("error") or tool_data.get("reward_info", {}).get("error_type") or "tool_call_failed"

    status, finish_data, latency = _request_json(
        "POST",
        f"{base_url}/episodes/{episode_id}/finish",
        {},
    )
    record["finish_status"] = status
    record["finish_latency"] = latency
    if status == 200 and finish_data.get("ok"):
        record["finish_ok"] = True
    elif record["error_type"] is None:
        record["error_type"] = finish_data.get("error") or "finish_failed"
    return record


def _health(base_url):
    status, data, _ = _request_json("GET", f"{base_url}/health")
    return status, data


def run_stress(base_url, concurrency, total_episodes):
    status, health_before = _health(base_url)
    if status != 200 or not health_before.get("ok"):
        raise RuntimeError(f"health_check_failed: {health_before}")

    status, catalog, _ = _request_json("GET", f"{base_url}/catalog/tasks")
    if status != 200 or not catalog.get("ok"):
        raise RuntimeError(f"catalog_fetch_failed: {catalog}")
    tasks = catalog.get("tasks") or []
    if not tasks:
        raise RuntimeError("catalog is empty")
    task_ids = [task["task_id"] for task in tasks]

    started = time.time()
    results = []
    lock = threading.Lock()

    def _worker(index):
        task_id = task_ids[index % len(task_ids)]
        result = _run_episode(base_url, task_id)
        with lock:
            results.append(result)
        return result

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(_worker, index) for index in range(total_episodes)]
        for _ in as_completed(futures):
            pass

    wall_seconds = time.time() - started
    status, health_after = _health(base_url)
    if status != 200 or not health_after.get("ok"):
        health_after = {"ok": False, "status": status, "payload": health_after}

    start_ok = sum(1 for item in results if item["start_ok"])
    tool_ok = sum(1 for item in results if item["tool_ok"])
    finish_ok = sum(1 for item in results if item["finish_ok"])
    latencies = {
        "start": [item["start_latency"] for item in results if item["start_latency"] is not None],
        "tool": [item["tool_latency"] for item in results if item["tool_latency"] is not None],
        "finish": [item["finish_latency"] for item in results if item["finish_latency"] is not None],
    }
    errors = {}
    for item in results:
        key = item.get("error_type") or ""
        if not key:
            continue
        errors[key] = errors.get(key, 0) + 1

    def _summary(values):
        if not values:
            return None
        return {
            "mean": statistics.mean(values),
            "p95": statistics.quantiles(values, n=20)[18] if len(values) >= 20 else max(values),
            "max": max(values),
        }

    return {
        "base_url": base_url,
        "concurrency": concurrency,
        "total_episodes": total_episodes,
        "wall_seconds": wall_seconds,
        "episodes_per_second": (total_episodes / wall_seconds) if wall_seconds else None,
        "start_ok": start_ok,
        "tool_ok": tool_ok,
        "finish_ok": finish_ok,
        "error_counts": errors,
        "latency_seconds": {
            "start": _summary(latencies["start"]),
            "tool": _summary(latencies["tool"]),
            "finish": _summary(latencies["finish"]),
        },
        "health_before": health_before,
        "health_after": health_after,
    }


def main():
    parser = argparse.ArgumentParser(description="Run a concurrency stress test against the tasksvc env server.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--concurrency", type=int, nargs="+", default=[64, 128, 192, 256])
    parser.add_argument("--episodes-per-level", type=int, default=256)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    summaries = []
    for level in args.concurrency:
        summaries.append(run_stress(args.base_url, level, args.episodes_per_level))

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"levels": summaries}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
