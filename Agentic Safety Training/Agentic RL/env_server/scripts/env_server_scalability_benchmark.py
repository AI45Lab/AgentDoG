import argparse
import concurrent.futures
import json
import os
import random
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


def _linspace_int(start, stop, count):
    if count <= 1:
        return [int(stop)]
    values = []
    for index in range(count):
        value = start + (stop - start) * index / (count - 1)
        values.append(int(round(value)))
    return values


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
            parsed = json.loads(body) if body else {}
            return resp.status, parsed, time.time() - started
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw_body": body}
        return exc.code, parsed, time.time() - started
    except Exception as exc:
        return 0, {"ok": False, "error": str(exc)}, time.time() - started


def _free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _read_proc_rss_mb(pid):
    try:
        with open(f"/proc/{pid}/status", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("VmRSS:"):
                    return float(line.split()[1]) / 1024.0
    except OSError:
        return None
    return None


def _read_cpu_percent(pid):
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "%cpu="],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        text = result.stdout.strip()
        return float(text) if text else None
    except Exception:
        return None


def _mem_available_mb():
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return float(line.split()[1]) / 1024.0
    except OSError:
        return None
    return None


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


class ResourceMonitor:
    def __init__(self, pid, interval=0.05):
        self.pid = pid
        self.interval = interval
        self.peak_rss_mb = 0.0
        self.peak_cpu_percent = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self):
        while not self._stop.is_set():
            rss = _read_proc_rss_mb(self.pid)
            cpu = _read_cpu_percent(self.pid)
            if rss is not None:
                self.peak_rss_mb = max(self.peak_rss_mb, rss)
            if cpu is not None:
                self.peak_cpu_percent = max(self.peak_cpu_percent, cpu)
            time.sleep(self.interval)


def _load_catalog(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    catalog = payload.get("runtime_catalog") if isinstance(payload, dict) else None
    if not isinstance(catalog, dict):
        raise ValueError(f"Expected runtime_catalog dict in {path}")
    return catalog


def _write_catalog_subset(full_catalog, size, output_path):
    items = list(full_catalog.items())[:size]
    payload = {"runtime_catalog": dict(items)}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return output_path


def _start_server(repo_root, catalog_file, port, log_file, *, max_episodes):
    cmd = [
        sys.executable,
        "-m",
        "tasksvc.runtime.server",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--catalog-file",
        str(catalog_file),
        "--max-episodes",
        str(max_episodes),
        "--episode-ttl-seconds",
        "3600",
        "--episode-max-steps",
        "6",
        "--tool-exec-timeout",
        "10",
    ]
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_handle = log_file.open("w", encoding="utf-8")
    before_available = _mem_available_mb()
    started = time.time()
    proc = subprocess.Popen(
        cmd,
        cwd=str(repo_root),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        while time.time() - started < 120:
            if proc.poll() is not None:
                raise RuntimeError(f"server exited early with code {proc.returncode}; see {log_file}")
            status, payload, _ = _request_json("GET", f"{base_url}/health", timeout=2)
            if status == 200 and payload.get("ok"):
                elapsed = time.time() - started
                rss = _read_proc_rss_mb(proc.pid)
                after_available = _mem_available_mb()
                system_delta = (
                    before_available - after_available
                    if before_available is not None and after_available is not None
                    else None
                )
                return proc, log_handle, base_url, elapsed, rss, system_delta
            time.sleep(0.1)
        raise TimeoutError(f"server did not become healthy within 120s; see {log_file}")
    except Exception:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log_handle.close()
        raise


def _stop_server(proc, log_handle):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
    log_handle.close()


def _catalog_task_ids(base_url):
    status, payload, _ = _request_json("GET", f"{base_url}/catalog/tasks", timeout=30)
    if status != 200 or not payload.get("ok"):
        raise RuntimeError(f"catalog_fetch_failed: {payload}")
    return [item["task_id"] for item in payload.get("tasks") or []]


def _start_episode(base_url, task_id):
    status, payload, _ = _request_json(
        "POST",
        f"{base_url}/episodes/start",
        {"task_id": task_id},
        timeout=30,
    )
    ok = status == 200 and payload.get("ok")
    return {
        "ok": bool(ok),
        "status": status,
        "episode_id": payload.get("episode_id"),
        "available_tools": payload.get("available_tools") or [],
        "error": None if ok else payload.get("error") or payload,
    }


def _finish_episode(base_url, episode_id):
    return _request_json("POST", f"{base_url}/episodes/{episode_id}/finish", {}, timeout=30)


def _run_episode_concurrency(base_url, task_ids, level, server_pid):
    random.seed(17 + level)
    chosen = [task_ids[index % len(task_ids)] for index in range(level)]
    started = time.time()
    with ResourceMonitor(server_pid) as monitor:
        with concurrent.futures.ThreadPoolExecutor(max_workers=level) as executor:
            futures = [executor.submit(_start_episode, base_url, task_id) for task_id in chosen]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
    elapsed = time.time() - started
    episode_ids = [item["episode_id"] for item in results if item.get("ok") and item.get("episode_id")]
    # Clean up after measuring the episode-start workload.
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(level, 256)) as executor:
        list(executor.map(lambda eid: _finish_episode(base_url, eid), episode_ids))
    return {
        "episodes": level,
        "ok": len(episode_ids),
        "elapsed_seconds": elapsed,
        "peak_rss_mb": monitor.peak_rss_mb,
        "peak_cpu_percent": monitor.peak_cpu_percent,
        "errors": len(results) - len(episode_ids),
    }


def _run_tool_call_concurrency(base_url, task_ids, level, server_pid):
    # Start episodes before the measured section, then concurrently execute one tool call.
    starts = []
    for index in range(level):
        start = _start_episode(base_url, task_ids[index % len(task_ids)])
        if start.get("ok") and start.get("available_tools"):
            starts.append(start)
    def _call_tool(start):
        tool_schema = start["available_tools"][0]
        tool_name = ((tool_schema or {}).get("function") or {}).get("name")
        args = _build_minimal_arguments(tool_schema)
        status, payload, _ = _request_json(
            "POST",
            f"{base_url}/episodes/{start['episode_id']}/tool-call",
            {"tool_name": tool_name, "arguments": args},
            timeout=60,
        )
        return status == 200 and payload.get("ok")

    started = time.time()
    with ResourceMonitor(server_pid) as monitor:
        with concurrent.futures.ThreadPoolExecutor(max_workers=level) as executor:
            results = [future.result() for future in concurrent.futures.as_completed([executor.submit(_call_tool, s) for s in starts])]
    elapsed = time.time() - started
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(level, 256)) as executor:
        list(executor.map(lambda s: _finish_episode(base_url, s["episode_id"]), starts))
    return {
        "tool_calls": level,
        "started_episodes": len(starts),
        "ok": sum(1 for item in results if item),
        "elapsed_seconds": elapsed,
        "peak_rss_mb": monitor.peak_rss_mb,
        "peak_cpu_percent": monitor.peak_cpu_percent,
        "errors": len(results) - sum(1 for item in results if item),
    }


def main():
    parser = argparse.ArgumentParser(description="Measure tasksvc server loading and concurrency scalability.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--catalog-10000", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--env-min", type=int, default=100)
    parser.add_argument("--env-max", type=int, default=10000)
    parser.add_argument("--concurrency-min", type=int, default=50)
    parser.add_argument("--concurrency-max", type=int, default=2000)
    parser.add_argument("--points", type=int, default=10)
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    output_dir = Path(args.output_dir)
    subset_dir = output_dir / "subsets"
    output_dir.mkdir(parents=True, exist_ok=True)

    env_points = _linspace_int(args.env_min, args.env_max, args.points)
    concurrency_points = _linspace_int(args.concurrency_min, args.concurrency_max, args.points)
    full_catalog = _load_catalog(args.catalog_10000)
    if len(full_catalog) < args.env_max:
        raise ValueError(f"catalog has {len(full_catalog)} tasks, expected at least {args.env_max}")

    loading_results = []
    for size in env_points:
        catalog_file = _write_catalog_subset(full_catalog, size, subset_dir / f"runtime_catalog_{size}.json")
        port = _free_port()
        proc, log_handle, base_url, startup, rss, system_delta = _start_server(
            repo_root,
            catalog_file,
            port,
            output_dir / "logs" / f"server_load_{size}.log",
            max_episodes=max(args.concurrency_max + 512, 4096),
        )
        try:
            loading_results.append({
                "envs": size,
                "startup_seconds": startup,
                "server_rss_mb": rss,
                "system_delta_mb": system_delta,
                "port": port,
            })
        finally:
            _stop_server(proc, log_handle)

    # Run concurrency tests on the max-size catalog.
    catalog_file = subset_dir / f"runtime_catalog_{args.env_max}.json"
    port = _free_port()
    proc, log_handle, base_url, startup, rss, system_delta = _start_server(
        repo_root,
        catalog_file,
        port,
        output_dir / "logs" / f"server_concurrency_{args.env_max}.log",
        max_episodes=max(args.concurrency_max * 3, 8192),
    )
    try:
        task_ids = _catalog_task_ids(base_url)
        episode_results = [
            _run_episode_concurrency(base_url, task_ids, level, proc.pid)
            for level in concurrency_points
        ]
        tool_results = [
            _run_tool_call_concurrency(base_url, task_ids, level, proc.pid)
            for level in concurrency_points
        ]
        concurrency_server = {
            "envs": args.env_max,
            "startup_seconds": startup,
            "server_rss_mb": rss,
            "system_delta_mb": system_delta,
            "port": port,
        }
    finally:
        _stop_server(proc, log_handle)

    payload = {
        "env_points": env_points,
        "concurrency_points": concurrency_points,
        "loading": loading_results,
        "concurrency_server": concurrency_server,
        "episode_concurrency": episode_results,
        "tool_call_concurrency": tool_results,
    }
    (output_dir / "scalability_benchmark.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
