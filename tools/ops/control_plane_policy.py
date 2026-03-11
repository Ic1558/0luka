from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.ops.control_plane_policy_guard import apply_auto_lane_guard
from tools.ops.control_plane_policy_observability import load_policy_stats
from tools.ops.control_plane_persistence import (
    DecisionPersistenceError,
    read_latest_decision,
    read_suggestion_feedback,
)
from tools.ops.control_plane_suggestions import load_latest_suggestion


POLICY_MANUAL_ONLY = "MANUAL_ONLY"
POLICY_HUMAN_APPROVAL_REQUIRED = "HUMAN_APPROVAL_REQUIRED"
POLICY_AUTO_ALLOWED = "AUTO_ALLOWED"

SAFE_LANE_NONE = "NONE"
SAFE_LANE_SUPERVISED_RETRY = "SUPERVISED_RETRY"
SAFE_LANE_SUPERVISED_ESCALATION = "SUPERVISED_ESCALATION"


def _alignment_count(rows: list[dict[str, Any]], *, operator_action: str) -> int:
    return sum(
        1
        for row in rows
        if row.get("alignment") == "MATCHED_SUGGESTION" and row.get("operator_action") == operator_action
    )


def derive_policy_verdict(
    latest_decision: dict[str, Any] | None,
    suggestion_payload: dict[str, Any],
    feedback_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    suggestion = str(suggestion_payload.get("suggestion") or "NO_ACTION_RECOMMENDED")
    confidence_band = str(suggestion_payload.get("confidence_band") or "LOW")
    execution_outcome = suggestion_payload.get("execution_outcome")
    decision_state = suggestion_payload.get("decision_state")
    base = {
        "decision_id": suggestion_payload.get("decision_id"),
        "trace_id": suggestion_payload.get("trace_id"),
        "suggestion": suggestion,
        "confidence_band": confidence_band,
        "alignment_count": 0,
    }

    if latest_decision is None:
        return {
            **base,
            "policy_verdict": POLICY_MANUAL_ONLY,
            "policy_reason": "no_latest_decision",
            "policy_safe_lane": SAFE_LANE_NONE,
        }
    if suggestion == "NO_ACTION_RECOMMENDED":
        return {
            **base,
            "policy_verdict": POLICY_MANUAL_ONLY,
            "policy_reason": "no_action_suggested",
            "policy_safe_lane": SAFE_LANE_NONE,
        }
    if suggestion == "RETRY_RECOMMENDED":
        alignment_count = _alignment_count(feedback_rows, operator_action="RETRY_EXECUTION")
        if (
            confidence_band == "HIGH"
            and decision_state == "APPROVED"
            and execution_outcome == "EXECUTION_FAILED"
            and alignment_count >= 2
        ):
            return {
                **base,
                "alignment_count": alignment_count,
                "policy_verdict": POLICY_AUTO_ALLOWED,
                "policy_reason": "high_confidence_retry_after_repeated_operator_alignment",
                "policy_safe_lane": SAFE_LANE_SUPERVISED_RETRY,
            }
        return {
            **base,
            "alignment_count": alignment_count,
            "policy_verdict": POLICY_HUMAN_APPROVAL_REQUIRED,
            "policy_reason": "retry_recommended_but_not_auto_eligible",
            "policy_safe_lane": SAFE_LANE_SUPERVISED_RETRY,
        }
    if suggestion == "ESCALATION_RECOMMENDED":
        return {
            **base,
            "policy_verdict": POLICY_HUMAN_APPROVAL_REQUIRED,
            "policy_reason": "escalation_recommended_but_manual_confirmation_required",
            "policy_safe_lane": SAFE_LANE_SUPERVISED_ESCALATION,
        }
    return {
        **base,
        "policy_verdict": POLICY_MANUAL_ONLY,
        "policy_reason": "policy_fallback_manual_only",
        "policy_safe_lane": SAFE_LANE_NONE,
    }


def load_latest_policy(
    *,
    runtime_root: Path,
    observability_root: Path,
    repo_root: Path,
) -> dict[str, Any]:
    try:
        latest = read_latest_decision(runtime_root)
    except DecisionPersistenceError:
        latest = None
    suggestion = load_latest_suggestion(
        runtime_root=runtime_root,
        observability_root=observability_root,
        repo_root=repo_root,
    )
    try:
        feedback = read_suggestion_feedback(
            observability_root,
            decision_id=latest.get("decision_id") if isinstance(latest, dict) else None,
            limit=50,
        )
    except DecisionPersistenceError:
        feedback = []
    base_policy = derive_policy_verdict(latest, suggestion, feedback)
    stats = load_policy_stats(observability_root=observability_root, repo_root=repo_root)
    return apply_auto_lane_guard(base_policy, stats)
