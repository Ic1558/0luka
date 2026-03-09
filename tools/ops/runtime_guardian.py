#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.activity_feed_guard import guarded_append_activity_feed
from core.config import RUNTIME_ROOT
from tools.ops import runtime_validator


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _guardian_actions_path() -> Path:
    return RUNTIME_ROOT / "state" / "guardian_actions.jsonl"


def _activity_feed_path() -> Path:
    return RUNTIME_ROOT / "logs" / "activity_feed.jsonl"


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _classify_action(report: dict[str, Any]) -> tuple[str, str, str]:
    errors = report.get("errors")
    if not isinstance(errors, list) or not errors:
        return "healthy", "none", "validator_clean"

    categories = {str(row.get("category") or "") for row in errors if isinstance(row, dict)}
    if "APPROVAL_ERROR" in categories:
        return "critical", "freeze_and_alert", "approval_violation_detected"
    if "QUEUE_ERROR" in categories:
        return "critical", "freeze_and_alert", "queue_corruption_detected"
    if "PROJECTION_DRIFT" in categories:
        return "high", "report_only", "projection_drift_detected"
    if "ARTIFACT_ERROR" in categories:
        return "high", "report_only", "artifact_integrity_failure"
    return "high", "report_only", "runtime_validation_failed"


def _activity_event(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "ts_utc": entry["timestamp"],
        "action": "guardian_recovery",
        "phase_id": "RUNTIME_GUARDIAN_V1",
        "status_badge": "PARTIAL",
        "tool": "runtime_guardian",
        "severity": entry["severity"],
        "guardian_action": entry["action"],
        "reason": entry["reason"],
        "run_id": entry.get("run_id"),
    }


def enforce_evidence_minimum(trace_id: str) -> dict[str, Any]:
    """
    Safe-scope guardian enforcement:
    - call validator verification chain
    - allow only if verified, otherwise freeze_and_alert
    Does not perform destructive remediation or mutate runtime state beyond existing logs/events.
    """
    verification = runtime_validator.run_verification_chain(trace_id)
    verdict = str(verification.get("verdict") or "")
    if verdict == "verified":
        return {
            "trace_id": str(trace_id),
            "guardian_action": "allow",
            "reason": "verified",
            "verification": verification,
        }
    return {
        "trace_id": str(trace_id),
        "guardian_action": "freeze_and_alert",
        "reason": "min_evidence_failed",
        "verification": verification,
    }


def run_once(*, mode: str = "full", strict_artifacts: bool = False) -> dict[str, Any]:
    report = runtime_validator.validate_runtime(mode=mode, strict_artifacts=strict_artifacts)
    severity, action, reason = _classify_action(report)
    first_run = None
    errors = report.get("errors")
    if isinstance(errors, list):
        for row in errors:
            if isinstance(row, dict) and row.get("run_id"):
                first_run = str(row["run_id"])
                break
    entry = {
        "timestamp": _utc_now(),
        "source": "runtime_guardian",
        "mode": mode,
        "runtime_status": report.get("runtime_status"),
        "severity": severity,
        "action": action,
        "reason": reason,
        "run_id": first_run,
        "error_count": len(errors) if isinstance(errors, list) else 0,
    }
    _append_jsonl(_guardian_actions_path(), entry)
    guarded_append_activity_feed(_activity_feed_path(), _activity_event(entry))
    return {"ok": True, "guardian_entry": entry, "validator_report": report}


def run_loop(*, interval_sec: float, mode: str = "full", strict_artifacts: bool = False) -> int:
    while True:
        run_once(mode=mode, strict_artifacts=strict_artifacts)
        time.sleep(interval_sec)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal runtime guardian for validator-driven protection.")
    parser.add_argument("--once", action="store_true", help="Run a single guardian pass and exit.")
    parser.add_argument("--quick", action="store_true", help="Use validator quick mode.")
    parser.add_argument("--artifacts", action="store_true", help="Enable strict artifact existence checks.")
    parser.add_argument("--interval-sec", type=float, default=300.0, help="Loop interval in seconds.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable result for --once.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    mode = "quick" if args.quick else "full"
    if args.once or args.json:
        payload = run_once(mode=mode, strict_artifacts=args.artifacts)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            print(json.dumps(payload["guardian_entry"], ensure_ascii=False))
        return 0
    return run_loop(interval_sec=max(args.interval_sec, 1.0), mode=mode, strict_artifacts=args.artifacts)


if __name__ == "__main__":
    raise SystemExit(main())
