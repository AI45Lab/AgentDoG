from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

from guardrail.config import GuardrailConfig
from guardrail.evaluator import GuardrailResult, evaluate


def run_guardrail_check(
    events_path: str | Path,
    config: GuardrailConfig,
    output_dir: str | Path | None = None,
) -> GuardrailResult:
    """Read a session_events.jsonl file, evaluate safety, write report.

    Args:
        events_path: Path to session_events.jsonl file.
        config: Guardrail configuration.
        output_dir: Directory to write guardrail_report.json. If None,
                    writes next to the events file.

    Returns:
        GuardrailResult with the evaluation outcome.
    """
    events_path = Path(events_path)
    session_events_text = events_path.read_text(encoding="utf-8")

    result = evaluate(session_events_text, config)

    # Determine output location
    if output_dir is not None:
        report_dir = Path(output_dir)
    else:
        report_dir = events_path.parent
    report_dir.mkdir(parents=True, exist_ok=True)

    report_path = report_dir / "guardrail_report.json"
    report_payload = {
        "prediction": result.prediction,
        "label": _prediction_label(result.prediction),
        "reason": result.reason,
        "model": result.model,
        "error": result.error,
        "events_file": str(events_path),
    }
    report_path.write_text(
        json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    # Alert on unsafe
    if result.prediction == 1:
        print(
            f"GUARDRAIL ALERT: unsafe trajectory detected in {events_path}\n"
            f"  Reason: {result.reason}",
            file=sys.stderr,
        )

    return result


def scan_artifacts_dir(
    artifacts_dir: str | Path,
    config: GuardrailConfig,
) -> list[dict]:
    """Recursively find all session_events.jsonl files and evaluate each."""
    artifacts_dir = Path(artifacts_dir)
    results: list[dict] = []

    events_files = sorted(artifacts_dir.rglob("session_events.jsonl"))
    if not events_files:
        print(f"No session_events.jsonl files found in {artifacts_dir}", file=sys.stderr)
        return results

    for events_path in events_files:
        print(f"Checking: {events_path}", file=sys.stderr)
        result = run_guardrail_check(events_path, config)
        results.append({
            "file": str(events_path),
            "prediction": result.prediction,
            "label": _prediction_label(result.prediction),
            "reason": result.reason,
            "error": result.error,
        })

    # Print summary
    total = len(results)
    safe = sum(1 for r in results if r["prediction"] == 0)
    unsafe = sum(1 for r in results if r["prediction"] == 1)
    errors = sum(1 for r in results if r["prediction"] == -1)
    print(
        f"\nScan complete: {total} trajectories, "
        f"{safe} safe, {unsafe} unsafe, {errors} errors",
        file=sys.stderr,
    )

    return results


def _prediction_label(prediction: int) -> str:
    if prediction == 0:
        return "safe"
    if prediction == 1:
        return "unsafe"
    return "error"
