from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from tools.ops.control_plane_auto_lane_review import derive_auto_lane_review
from tools.ops.control_plane_persistence import DecisionPersistenceError, read_decision_history
from tools.ops.control_plane_policy_guard import derive_auto_lane_guard
from tools.ops.control_plane_policy_observability import load_policy_stats
from tools.ops.execution_outcome_reconciler import reconcile_execution_outcome


def _category(review: dict[str, Any]) -> str:
    if review.get("eligibility_verdict") == "ELIGIBLE":
        return "ELIGIBLE"
    reasons = review.get("reasons")
    if isinstance(reasons, list) and len(reasons) == 1:
        return "NEAR_MISS"
    return "BLOCKED_MULTI"


def _latest_rows_by_decision(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for row in reversed(rows):
        decision_id = str(row.get("decision_id") or "").strip()
        if not decision_id or decision_id in seen:
            continue
        seen.add(decision_id)
        items.append(row)
        if len(items) >= limit:
            break
    return items


def _policy_payload_for_decision(rows: list[dict[str, Any]], decision_id: str, auto_lane_state: str) -> dict[str, Any]:
    policy_row: dict[str, Any] | None = None
    for row in reversed(rows):
        if str(row.get("decision_id") or "") != decision_id:
            continue
        if row.get("event") == "POLICY_EVALUATED":
            policy_row = row
            break
    suggestion = policy_row.get("suggestion") if isinstance(policy_row, dict) else None
    return {
        "decision_id": policy_row.get("decision_id") if isinstance(policy_row, dict) else None,
        "trace_id": policy_row.get("trace_id") if isinstance(policy_row, dict) else None,
        "suggestion": suggestion,
        "policy_verdict": policy_row.get("policy_verdict") if isinstance(policy_row, dict) else None,
        "policy_safe_lane": "SUPERVISED_RETRY" if suggestion == "RETRY_RECOMMENDED" else "NONE",
        "confidence_band": policy_row.get("confidence_band") if isinstance(policy_row, dict) else None,
        "alignment_count": int(policy_row.get("alignment_count") or 0) if isinstance(policy_row, dict) else 0,
        "auto_lane_state": auto_lane_state,
    }


def _decision_payload(row: dict[str, Any], *, repo_root: Path, observability_root: Path) -> dict[str, Any]:
    payload = {
        "decision_id": row.get("decision_id"),
        "trace_id": row.get("trace_id"),
        "signal_received": row.get("signal_received"),
        "proposed_action": row.get("proposed_action"),
        "evidence_refs": row.get("evidence_refs") if isinstance(row.get("evidence_refs"), list) else [],
        "ts_utc": row.get("ts_utc"),
        "operator_status": row.get("operator_status"),
        "operator_note": row.get("operator_note"),
    }
    payload["execution"] = reconcile_execution_outcome(
        payload,
        repo_root=repo_root,
        observability_root=observability_root,
    )
    return payload


def load_auto_lane_candidate_queue(
    *,
    observability_root: Path,
    repo_root: Path,
    item_limit: int = 10,
) -> dict[str, Any]:
    try:
        rows = read_decision_history(observability_root, limit=200)
    except DecisionPersistenceError:
        return {
            "items": [],
            "summary": {"eligible_count": 0, "blocked_count": 0, "top_blockers": []},
        }

    stats = load_policy_stats(observability_root=observability_root, repo_root=repo_root)
    guard = derive_auto_lane_guard(stats)
    auto_lane_state = str(guard.get("auto_lane_state") or "AUTO_LANE_FROZEN")

    items: list[dict[str, Any]] = []
    blocker_counts: Counter[str] = Counter()

    for row in _latest_rows_by_decision(rows, limit=item_limit):
        decision_id = str(row.get("decision_id") or "")
        decision_payload = _decision_payload(row, repo_root=repo_root, observability_root=observability_root)
        policy_payload = _policy_payload_for_decision(rows, decision_id, auto_lane_state)
        review = derive_auto_lane_review(decision_payload, policy_payload)
        category = _category(review)
        for reason in review.get("reasons") or []:
            blocker_counts[str(reason)] += 1
        items.append(
            {
                "decision_id": review.get("decision_id"),
                "trace_id": review.get("trace_id"),
                "candidate_lane": review.get("candidate_lane"),
                "eligibility_verdict": review.get("eligibility_verdict"),
                "category": category,
                "effective_lane_state": review.get("effective_lane_state"),
                "reasons": review.get("reasons", []),
                "summary": review.get("summary"),
            }
        )

    summary = {
        "eligible_count": sum(1 for item in items if item.get("eligibility_verdict") == "ELIGIBLE"),
        "blocked_count": sum(1 for item in items if item.get("eligibility_verdict") == "BLOCKED"),
        "top_blockers": [
            {"reason": reason, "count": count}
            for reason, count in blocker_counts.most_common(5)
        ],
    }
    return {"items": items, "summary": summary}
