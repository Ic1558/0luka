from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.ops.control_plane_policy_observability import (
    FAILURE_AUDIT_DECISIONS,
    SUCCESS_STATUSES,
    load_policy_stats,
)
from tools.ops.control_plane_persistence import DecisionPersistenceError, read_decision_history


MAX_REASON_BREAKDOWN = 5


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


def _empty_review(stats: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy_state": stats.get("policy_state", "POLICY_HEALTHY"),
        "auto_lane_state": stats.get("auto_lane_state", "AUTO_LANE_FROZEN"),
        "totals": {
            "policy_evaluations": 0,
            "auto_retry_triggered": int(stats.get("auto_retry_triggered") or 0),
            "auto_retry_success": int(stats.get("auto_retry_success") or 0),
            "auto_retry_failed": int(stats.get("auto_retry_failed") or 0),
            "alignment_match": int(stats.get("alignment_match") or 0),
            "alignment_mismatch": int(stats.get("alignment_mismatch") or 0),
        },
        "rates": {
            "auto_retry_success_rate": float(stats.get("success_rate") or 0.0),
            "operator_alignment_rate": float(stats.get("operator_alignment_rate") or 0.0),
        },
        "reason_breakdown": [],
        "review_flags": ["review_insufficient_evidence"],
        "review_summary": "insufficient evidence for strong review conclusions",
    }


def derive_policy_review(rows: list[dict[str, Any]], *, repo_root: Path, stats: dict[str, Any]) -> dict[str, Any]:
    if not rows:
        return _empty_review(stats)

    policy_evaluations = 0
    reason_counts: dict[str, dict[str, int | str]] = {}
    retry_request_counts: dict[str, int] = {}

    for row in rows:
        event = str(row.get("event") or "")
        decision_id = str(row.get("decision_id") or "")
        if event == "POLICY_EVALUATED":
            policy_evaluations += 1
            reason = str(row.get("policy_reason") or "unknown_policy_reason")
            bucket = reason_counts.setdefault(
                reason,
                {
                    "policy_reason": reason,
                    "count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                },
            )
            bucket["count"] = int(bucket["count"]) + 1
        elif event == "EXECUTION_RETRY_REQUESTED" and decision_id:
            retry_request_counts[decision_id] = retry_request_counts.get(decision_id, 0) + 1
        elif event == "AUTO_RETRY_TRIGGERED" and decision_id:
            reason = str(row.get("policy_reason") or "unknown_policy_reason")
            bucket = reason_counts.setdefault(
                reason,
                {
                    "policy_reason": reason,
                    "count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                },
            )
            retry_count = retry_request_counts.get(decision_id, 0)
            if retry_count < 1:
                continue
            outcome = _auto_retry_outcome(f"decision_exec_{decision_id}_retry_{retry_count}", repo_root=repo_root)
            if outcome == "success":
                bucket["success_count"] = int(bucket["success_count"]) + 1
            elif outcome == "failed":
                bucket["failure_count"] = int(bucket["failure_count"]) + 1

    totals = {
        "policy_evaluations": policy_evaluations,
        "auto_retry_triggered": int(stats.get("auto_retry_triggered") or 0),
        "auto_retry_success": int(stats.get("auto_retry_success") or 0),
        "auto_retry_failed": int(stats.get("auto_retry_failed") or 0),
        "alignment_match": int(stats.get("alignment_match") or 0),
        "alignment_mismatch": int(stats.get("alignment_mismatch") or 0),
    }
    rates = {
        "auto_retry_success_rate": float(stats.get("success_rate") or 0.0),
        "operator_alignment_rate": float(stats.get("operator_alignment_rate") or 0.0),
    }

    flags: list[str] = []
    sparse = policy_evaluations < 3 and totals["auto_retry_triggered"] < 3
    if sparse:
        flags.append("review_insufficient_evidence")
    else:
        if totals["auto_retry_triggered"] and rates["auto_retry_success_rate"] < 0.70:
            flags.append("review_auto_retry_threshold")
        alignment_total = totals["alignment_match"] + totals["alignment_mismatch"]
        if alignment_total and rates["operator_alignment_rate"] < 0.75:
            flags.append("review_alignment_drift")
        if str(stats.get("policy_state") or "") == "POLICY_DEGRADED":
            flags.append("review_frozen_lane")
        if any(int(item["failure_count"]) >= 3 for item in reason_counts.values()):
            flags.append("review_reason_failure_cluster")

    if flags == ["review_insufficient_evidence"]:
        review_summary = "insufficient evidence for strong review conclusions"
    elif "review_auto_retry_threshold" in flags and "review_alignment_drift" in flags:
        review_summary = "policy review recommended due to degraded auto-retry reliability and reduced operator alignment"
    elif "review_reason_failure_cluster" in flags:
        review_summary = "policy review recommended due to repeated failures concentrated in one policy reason"
    elif "review_auto_retry_threshold" in flags:
        review_summary = "policy review recommended due to degraded auto-retry reliability"
    elif "review_alignment_drift" in flags:
        review_summary = "policy review recommended due to reduced operator alignment"
    elif "review_frozen_lane" in flags:
        review_summary = "policy review recommended because the narrow auto-retry lane is currently frozen"
    else:
        review_summary = "policy review currently shows no strong adjustment signal"

    breakdown = sorted(
        (
            {
                "policy_reason": str(item["policy_reason"]),
                "count": int(item["count"]),
                "success_count": int(item["success_count"]),
                "failure_count": int(item["failure_count"]),
            }
            for item in reason_counts.values()
        ),
        key=lambda item: (-item["count"], item["policy_reason"]),
    )[:MAX_REASON_BREAKDOWN]

    return {
        "policy_state": stats.get("policy_state", "POLICY_HEALTHY"),
        "auto_lane_state": stats.get("auto_lane_state", "AUTO_LANE_FROZEN"),
        "totals": totals,
        "rates": rates,
        "reason_breakdown": breakdown,
        "review_flags": flags,
        "review_summary": review_summary,
    }


def load_policy_learning_review(*, observability_root: Path, repo_root: Path) -> dict[str, Any]:
    stats = load_policy_stats(observability_root=observability_root, repo_root=repo_root)
    try:
        rows = read_decision_history(observability_root, limit=200)
    except DecisionPersistenceError:
        rows = []
    return derive_policy_review(rows, repo_root=repo_root, stats=stats)
