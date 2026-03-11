from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.ops.control_plane_policy_guard import derive_auto_lane_guard
from tools.ops.control_plane_persistence import DecisionPersistenceError, read_decision_history


SUCCESS_STATUSES = {"committed", "ok", "success", "completed", "dry_run_ok"}
FAILURE_AUDIT_DECISIONS = {"rejected", "error"}


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("invalid_json_object")
    return payload


def _auto_retry_outcome(task_id: str, *, repo_root: Path) -> str:
    outbox_path = repo_root / "interface" / "outbox" / "tasks" / f"{task_id}.result.json"
    audit_path = repo_root / "observability" / "artifacts" / "router_audit" / f"{task_id}.json"

    if outbox_path.exists():
        try:
            payload = _read_json(outbox_path)
        except Exception:
            return "unknown"
        status = str(payload.get("status") or "").strip().lower()
        if status in SUCCESS_STATUSES:
            return "success"
        return "unknown"

    if audit_path.exists():
        try:
            payload = _read_json(audit_path)
        except Exception:
            return "unknown"
        decision_value = str(payload.get("decision") or "").strip().lower()
        if decision_value in FAILURE_AUDIT_DECISIONS:
            return "failed"
        return "unknown"

    return "unknown"


def derive_policy_stats(rows: list[dict[str, Any]], *, repo_root: Path) -> dict[str, Any]:
    retry_request_counts: dict[str, int] = {}
    auto_retry_triggered = 0
    auto_retry_success = 0
    auto_retry_failed = 0
    alignment_match = 0
    alignment_mismatch = 0

    for row in rows:
        decision_id = str(row.get("decision_id") or "")
        event = str(row.get("event") or "")
        if event == "EXECUTION_RETRY_REQUESTED" and decision_id:
            retry_request_counts[decision_id] = retry_request_counts.get(decision_id, 0) + 1
            continue
        if event == "AUTO_RETRY_TRIGGERED" and decision_id:
            auto_retry_triggered += 1
            retry_count = retry_request_counts.get(decision_id, 0)
            if retry_count < 1:
                continue
            outcome = _auto_retry_outcome(f"decision_exec_{decision_id}_retry_{retry_count}", repo_root=repo_root)
            if outcome == "success":
                auto_retry_success += 1
            elif outcome == "failed":
                auto_retry_failed += 1
            continue
        if event == "POLICY_ALIGNMENT_MATCHED":
            alignment_match += 1
            continue
        if event == "POLICY_ALIGNMENT_MISMATCHED":
            alignment_mismatch += 1

    success_rate = (auto_retry_success / auto_retry_triggered) if auto_retry_triggered else 0.0
    failure_rate = (auto_retry_failed / auto_retry_triggered) if auto_retry_triggered else 0.0
    policy_state = "POLICY_DEGRADED" if auto_retry_triggered and failure_rate > 0.30 else "POLICY_HEALTHY"
    operator_alignment_rate = (
        alignment_match / (alignment_match + alignment_mismatch)
        if (alignment_match + alignment_mismatch)
        else 0.0
    )

    payload = {
        "stats_available": True,
        "auto_retry_triggered": auto_retry_triggered,
        "auto_retry_success": auto_retry_success,
        "auto_retry_failed": auto_retry_failed,
        "alignment_match": alignment_match,
        "alignment_mismatch": alignment_mismatch,
        "success_rate": round(success_rate, 2),
        "operator_alignment_rate": round(operator_alignment_rate, 2),
        "policy_state": policy_state,
        "warning": "Policy reliability degraded. Review recommended." if policy_state == "POLICY_DEGRADED" else None,
    }
    payload.update(derive_auto_lane_guard(payload))
    return payload


def load_policy_stats(*, observability_root: Path, repo_root: Path) -> dict[str, Any]:
    try:
        rows = read_decision_history(observability_root, limit=200)
    except DecisionPersistenceError:
        payload = {
            "stats_available": False,
            "auto_retry_triggered": 0,
            "auto_retry_success": 0,
            "auto_retry_failed": 0,
            "alignment_match": 0,
            "alignment_mismatch": 0,
            "success_rate": 0.0,
            "operator_alignment_rate": 0.0,
            "policy_state": "POLICY_DEGRADED",
            "warning": "Policy reliability degraded. Review recommended.",
        }
        payload.update(derive_auto_lane_guard(payload))
        return payload
    return derive_policy_stats(rows, repo_root=repo_root)
