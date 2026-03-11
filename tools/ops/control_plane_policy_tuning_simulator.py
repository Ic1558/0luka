from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.ops.control_plane_policy_learning_review import _auto_retry_outcome
from tools.ops.control_plane_persistence import DecisionPersistenceError, read_decision_history


BASELINE_SUCCESS_THRESHOLD = 0.70


def _coerce_threshold(value: Any) -> float:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError as exc:
            raise ValueError("invalid_success_threshold") from exc
    if not isinstance(value, (int, float)):
        raise ValueError("invalid_success_threshold")
    threshold = float(value)
    if threshold < 0.0 or threshold > 1.0:
        raise ValueError("invalid_success_threshold")
    return round(threshold, 2)


def _build_reason_stats(rows: list[dict[str, Any]], *, repo_root: Path) -> dict[str, dict[str, Any]]:
    retry_request_counts: dict[str, int] = {}
    reason_stats: dict[str, dict[str, Any]] = {}

    for row in rows:
        event = str(row.get("event") or "")
        decision_id = str(row.get("decision_id") or "")
        if event == "EXECUTION_RETRY_REQUESTED" and decision_id:
            retry_request_counts[decision_id] = retry_request_counts.get(decision_id, 0) + 1
            continue
        if event != "AUTO_RETRY_TRIGGERED" or not decision_id:
            continue

        reason = str(row.get("policy_reason") or "unknown_policy_reason")
        bucket = reason_stats.setdefault(
            reason,
            {
                "policy_reason": reason,
                "triggered": 0,
                "success": 0,
                "failed": 0,
            },
        )
        bucket["triggered"] = int(bucket["triggered"]) + 1

        retry_count = retry_request_counts.get(decision_id, 0)
        if retry_count < 1:
            continue
        outcome = _auto_retry_outcome(f"decision_exec_{decision_id}_retry_{retry_count}", repo_root=repo_root)
        if outcome == "success":
            bucket["success"] = int(bucket["success"]) + 1
        elif outcome == "failed":
            bucket["failed"] = int(bucket["failed"]) + 1

    return reason_stats


def _aggregate_preview(reason_stats: dict[str, dict[str, Any]], *, threshold: float) -> dict[str, float | int]:
    retries_allowed = 0
    success_total = 0
    evaluated_reasons = 0

    for item in reason_stats.values():
        triggered = int(item["triggered"])
        success = int(item["success"])
        failed = int(item["failed"])
        known = success + failed
        if known < 1:
            continue
        evaluated_reasons += 1
        observed_success_rate = success / known
        if observed_success_rate >= threshold:
            retries_allowed += triggered
            success_total += success

    success_rate = (success_total / retries_allowed) if retries_allowed else 0.0
    return {
        "threshold": round(threshold, 2),
        "retries_allowed": retries_allowed,
        "success_rate": round(success_rate, 2),
        "evaluated_reasons": evaluated_reasons,
    }


def derive_tuning_preview(rows: list[dict[str, Any]], *, repo_root: Path, simulated_success_threshold: float) -> dict[str, Any]:
    threshold = _coerce_threshold(simulated_success_threshold)
    reason_stats = _build_reason_stats(rows, repo_root=repo_root)
    if not reason_stats:
        return {
            "baseline_threshold": BASELINE_SUCCESS_THRESHOLD,
            "simulated_threshold": threshold,
            "baseline_retry_count": 0,
            "simulated_retry_count": 0,
            "baseline_success_rate": 0.0,
            "simulated_success_rate": 0.0,
            "difference": {
                "retry_reduction": 0,
                "expected_success_gain": 0.0,
            },
            "stats_available": False,
        }

    baseline = _aggregate_preview(reason_stats, threshold=BASELINE_SUCCESS_THRESHOLD)
    simulated = _aggregate_preview(reason_stats, threshold=threshold)
    return {
        "baseline_threshold": baseline["threshold"],
        "simulated_threshold": simulated["threshold"],
        "baseline_retry_count": baseline["retries_allowed"],
        "simulated_retry_count": simulated["retries_allowed"],
        "baseline_success_rate": baseline["success_rate"],
        "simulated_success_rate": simulated["success_rate"],
        "difference": {
            "retry_reduction": int(baseline["retries_allowed"]) - int(simulated["retries_allowed"]),
            "expected_success_gain": round(float(simulated["success_rate"]) - float(baseline["success_rate"]), 2),
        },
        "stats_available": bool(baseline["evaluated_reasons"]),
    }


def load_policy_tuning_preview(
    *,
    observability_root: Path,
    repo_root: Path,
    simulated_success_threshold: float | str,
) -> dict[str, Any]:
    try:
        rows = read_decision_history(observability_root, limit=200)
    except DecisionPersistenceError:
        rows = []
    return derive_tuning_preview(
        rows,
        repo_root=repo_root,
        simulated_success_threshold=_coerce_threshold(simulated_success_threshold),
    )
