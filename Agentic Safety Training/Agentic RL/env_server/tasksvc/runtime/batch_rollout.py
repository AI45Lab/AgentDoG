import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from tasksvc.runtime.agent_rollout import AgentRolloutConfig, _http_get_json, _http_post_json, run_agent_episode


def _slugify(value):
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "task"))
    return text.strip("_") or "task"


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@dataclass
class BatchRolloutConfig:
    max_workers: int = 8


class BatchRolloutRecorder:
    def __init__(self, output_dir, benchmark=None):
        self.output_dir = Path(output_dir)
        self.results_dir = self.output_dir / "results"
        self.benchmark = benchmark
        self._lock = threading.Lock()
        self._task_ids = []
        self._completed = []
        self._failed = []
        self._errored = []
        self._risk_enabled = []
        self._risk_triggered = []
        self._benign_and_risk = []
        self._benign_only = []
        self._risk_only = []
        self._neither = []
        self._utility_success = []
        self._utility_under_attack_success = []
        self._attack_success = []
        self._tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self._start_time = time.time()
        self._write_state()

    def set_task_ids(self, task_ids):
        with self._lock:
            self._task_ids = list(task_ids)
            self._write_state()

    def record_result(self, task_id, payload):
        task_file = self.results_dir / f"{_slugify(task_id)}.json"
        status = payload.get("status") or "error"
        risk_enabled = bool(payload.get("risk_enabled"))
        risk_success = bool(payload.get("risk_success"))
        clean_task_success = bool(payload.get("clean_task_success", payload.get("task_success")))
        attacked_task_success = bool(payload.get("attacked_task_success"))
        usage = payload.get("llm_usage_summary") or {}
        with self._lock:
            _write_json(task_file, payload)
            if status == "success":
                self._completed.append(task_id)
            elif status == "failure":
                self._failed.append(task_id)
            else:
                self._errored.append(task_id)
            if risk_enabled:
                self._risk_enabled.append(task_id)
                if risk_success:
                    self._risk_triggered.append(task_id)
                if attacked_task_success and risk_success:
                    self._benign_and_risk.append(task_id)
                elif attacked_task_success and not risk_success:
                    self._benign_only.append(task_id)
                elif (not attacked_task_success) and risk_success:
                    self._risk_only.append(task_id)
                else:
                    self._neither.append(task_id)
            if clean_task_success:
                self._utility_success.append(task_id)
            if attacked_task_success:
                self._utility_under_attack_success.append(task_id)
            if risk_success:
                self._attack_success.append(task_id)
            self._tokens["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
            self._tokens["completion_tokens"] += int(usage.get("completion_tokens") or 0)
            self._tokens["total_tokens"] += int(usage.get("total_tokens") or 0)
            self._write_state()

    def finalize(self):
        with self._lock:
            self._write_state(finalized=True)

    def _write_state(self, finalized=False):
        manifest = {
            "benchmark": self.benchmark,
            "total_tasks": len(self._task_ids),
            "completed": len(self._completed),
            "failed": len(self._failed),
            "errored": len(self._errored),
            "completed_task_ids": list(self._completed),
            "failed_task_ids": list(self._failed),
            "errored_task_ids": list(self._errored),
            "risk_enabled_tasks": list(self._risk_enabled),
            "risk_triggered_task_ids": list(self._risk_triggered),
            "utility_success_task_ids": list(self._utility_success),
            "utility_under_attack_success_task_ids": list(self._utility_under_attack_success),
            "attack_success_task_ids": list(self._attack_success),
            "benign_and_risk_task_ids": list(self._benign_and_risk),
            "benign_only_task_ids": list(self._benign_only),
            "risk_only_task_ids": list(self._risk_only),
            "neither_goal_task_ids": list(self._neither),
            "updated_at": time.time(),
        }
        summary = {
            "benchmark": self.benchmark,
            "total_tasks": len(self._task_ids),
            "finished_tasks": len(self._completed) + len(self._failed) + len(self._errored),
            "successful_tasks": len(self._completed),
            "failed_tasks": len(self._failed),
            "errored_tasks": len(self._errored),
            "risk_enabled_tasks": len(self._risk_enabled),
            "risk_triggered_tasks": len(self._risk_triggered),
            "utility_success_tasks": len(self._utility_success),
            "utility_under_attack_success_tasks": len(self._utility_under_attack_success),
            "attack_success_tasks": len(self._attack_success),
            "benign_and_risk_tasks": len(self._benign_and_risk),
            "benign_only_tasks": len(self._benign_only),
            "risk_only_tasks": len(self._risk_only),
            "neither_goal_tasks": len(self._neither),
            "llm_usage_summary": dict(self._tokens),
            "elapsed_seconds": round(time.time() - self._start_time, 2),
            "done": finalized,
        }
        _write_json(self.output_dir / "manifest.json", manifest)
        _write_json(self.output_dir / "summary.json", summary)


def _load_task_entries_from_server(server_url):
    status, payload = _http_get_json(f"{server_url.rstrip('/')}/catalog/tasks")
    if status >= 400 or not payload.get("ok"):
        raise RuntimeError(f"Failed to load catalog tasks: {payload}")
    tasks = payload.get("tasks") or []
    return [item for item in tasks if isinstance(item, dict) and item.get("task_id")]


def _classify_rollout_result(result):
    if result.get("clean_task_success", result.get("task_success")):
        return "success"
    return "failure"


def run_agent_batch(
    server_url,
    llm_client_factory,
    task_ids=None,
    catalog_payload=None,
    rollout_config=None,
    batch_config=None,
    output_dir=None,
    benchmark=None,
):
    config = rollout_config or AgentRolloutConfig()
    batch = batch_config or BatchRolloutConfig()
    server_url = server_url.rstrip("/")

    registration = None
    resolved_task_ids = list(task_ids or [])
    if catalog_payload is not None:
        endpoint = "/catalog/register-batch" if (
            isinstance(catalog_payload, list)
            or (isinstance(catalog_payload, dict) and (
                "runtime_catalog" in catalog_payload or "task_drafts" in catalog_payload
            ))
        ) else "/catalog/register"
        status, registration = _http_post_json(f"{server_url}{endpoint}", catalog_payload)
        if status >= 400 or not registration.get("ok"):
            raise RuntimeError(f"Catalog registration failed: {registration}")
        if not resolved_task_ids:
            resolved_task_ids = list(registration.get("task_ids") or [])
            if not resolved_task_ids and registration.get("task_id"):
                resolved_task_ids = [registration["task_id"]]

    if not resolved_task_ids:
        resolved_task_ids = [item["task_id"] for item in _load_task_entries_from_server(server_url)]
    if not resolved_task_ids:
        raise RuntimeError("run_agent_batch requires task_ids or a catalog payload that resolves to at least one task.")

    recorder = BatchRolloutRecorder(output_dir, benchmark=benchmark) if output_dir else None
    if recorder:
        recorder.set_task_ids(resolved_task_ids)

    task_entries = {item["task_id"]: item for item in _load_task_entries_from_server(server_url)}

    def _merge_usage(*payloads):
        summary = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for payload in payloads:
            usage = (payload or {}).get("llm_usage_summary") or {}
            summary["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
            summary["completion_tokens"] += int(usage.get("completion_tokens") or 0)
            summary["total_tokens"] += int(usage.get("total_tokens") or 0)
        return summary

    def _run_pair(task_id):
        clean_result = run_agent_episode(
            server_url=server_url,
            llm_client=llm_client_factory(),
            task_id=task_id,
            catalog_payload=None,
            rollout_config=config,
            scenario="clean",
        )
        attacked_result = run_agent_episode(
            server_url=server_url,
            llm_client=llm_client_factory(),
            task_id=task_id,
            catalog_payload=None,
            rollout_config=config,
            scenario="attacked",
        )
        payload = {
            "ok": True,
            "task_id": task_id,
            "pair_id": task_id,
            "status": "success" if bool(clean_result.get("task_success")) else "failure",
            "task_success": bool(clean_result.get("task_success")),
            "clean_task_success": bool(clean_result.get("task_success")),
            "attacked_task_success": bool(attacked_result.get("task_success")),
            "risk_enabled": bool(attacked_result.get("risk_enabled")),
            "risk_success": bool(attacked_result.get("risk_success")),
            "scenario_results": {
                "clean": clean_result,
                "attacked": attacked_result,
            },
            "llm_usage_summary": _merge_usage(clean_result, attacked_result),
        }
        return payload

    def _run_one(task_id):
        entry = task_entries.get(task_id) or {}
        scenarios = {str(item).strip() for item in (entry.get("available_scenarios") or ["clean"])}
        try:
            if "attacked" in scenarios:
                payload = _run_pair(task_id)
            else:
                result = run_agent_episode(
                    server_url=server_url,
                    llm_client=llm_client_factory(),
                    task_id=task_id,
                    catalog_payload=None,
                    rollout_config=config,
                    scenario="clean",
                )
                payload = dict(result)
                payload["clean_task_success"] = bool(result.get("task_success"))
                payload.setdefault("attacked_task_success", False)
                payload["status"] = _classify_rollout_result(payload)
        except Exception as exc:  # noqa: BLE001
            payload = {
                "ok": False,
                "task_id": task_id,
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "llm_usage_summary": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
        if recorder:
            recorder.record_result(task_id, payload)
        return payload

    results = []
    with ThreadPoolExecutor(max_workers=max(1, int(batch.max_workers))) as executor:
        futures = {executor.submit(_run_one, task_id): task_id for task_id in resolved_task_ids}
        for future in as_completed(futures):
            results.append(future.result())

    if recorder:
        recorder.finalize()

    summary = {
        "benchmark": benchmark,
        "task_count": len(resolved_task_ids),
        "successful_tasks": sum(1 for item in results if item.get("status") == "success"),
        "failed_tasks": sum(1 for item in results if item.get("status") == "failure"),
        "errored_tasks": sum(1 for item in results if item.get("status") == "error"),
        "utility_success_tasks": sum(1 for item in results if item.get("clean_task_success", item.get("task_success"))),
        "utility_under_attack_success_tasks": sum(1 for item in results if item.get("attacked_task_success")),
        "attack_success_tasks": sum(1 for item in results if item.get("risk_success")),
        "risk_enabled_tasks": sum(1 for item in results if item.get("risk_enabled")),
        "risk_triggered_tasks": sum(1 for item in results if item.get("risk_success")),
        "benign_and_risk_tasks": sum(
            1 for item in results if item.get("attacked_task_success", item.get("task_success")) and item.get("risk_success")
        ),
        "benign_only_tasks": sum(
            1 for item in results if item.get("attacked_task_success", item.get("task_success")) and not item.get("risk_success")
        ),
        "risk_only_tasks": sum(
            1 for item in results if (not item.get("attacked_task_success", item.get("task_success"))) and item.get("risk_success")
        ),
        "neither_goal_tasks": sum(
            1
            for item in results
            if item.get("risk_enabled")
            and (not item.get("attacked_task_success", item.get("task_success")))
            and (not item.get("risk_success"))
        ),
        "llm_usage_summary": {
            "prompt_tokens": sum(int((item.get("llm_usage_summary") or {}).get("prompt_tokens") or 0) for item in results),
            "completion_tokens": sum(int((item.get("llm_usage_summary") or {}).get("completion_tokens") or 0) for item in results),
            "total_tokens": sum(int((item.get("llm_usage_summary") or {}).get("total_tokens") or 0) for item in results),
        },
    }
    return {
        "ok": True,
        "benchmark": benchmark,
        "task_ids": resolved_task_ids,
        "registration": registration,
        "summary": summary,
        "results": results,
    }

