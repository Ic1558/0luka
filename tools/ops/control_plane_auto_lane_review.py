from __future__ import annotations

from typing import Any


CANDIDATE_LANE = "SUPERVISED_RETRY"
ELIGIBLE = "ELIGIBLE"
BLOCKED = "BLOCKED"

FAILED_REASON_LABELS = {
    "no_latest_decision": "no latest decision is available",
    "suggestion_not_retry_recommended": "suggestion is not retry recommended",
    "policy_verdict_not_auto_allowed": "policy verdict is not auto allowed",
    "policy_safe_lane_not_supervised_retry": "policy safe lane is not supervised retry",
    "confidence_band_not_high": "confidence is below HIGH",
    "latest_decision_not_approved": "latest decision is not approved",
    "execution_outcome_not_failed": "execution outcome is not failed",
    "trust_alignment_count_below_threshold": "trust alignment count is below threshold",
    "auto_lane_frozen": "auto lane is frozen",
    "insufficient_eligibility_evidence": "insufficient eligibility evidence is available",
}


def _check_map(latest_decision: dict[str, Any] | None, policy_payload: dict[str, Any] | None) -> dict[str, bool]:
    execution = latest_decision.get("execution") if isinstance(latest_decision, dict) else None
    outcome_status = execution.get("outcome_status") if isinstance(execution, dict) else None
    alignment_count = policy_payload.get("alignment_count") if isinstance(policy_payload, dict) else None
    auto_lane_state = policy_payload.get("auto_lane_state") if isinstance(policy_payload, dict) else None
    return {
        "suggestion_retry_recommended": bool(
            isinstance(policy_payload, dict) and policy_payload.get("suggestion") == "RETRY_RECOMMENDED"
        ),
        "policy_verdict_auto_allowed": bool(
            isinstance(policy_payload, dict) and policy_payload.get("policy_verdict") == "AUTO_ALLOWED"
        ),
        "policy_safe_lane_supervised_retry": bool(
            isinstance(policy_payload, dict) and policy_payload.get("policy_safe_lane") == CANDIDATE_LANE
        ),
        "confidence_high": bool(
            isinstance(policy_payload, dict) and policy_payload.get("confidence_band") == "HIGH"
        ),
        "latest_decision_approved": bool(
            isinstance(latest_decision, dict) and latest_decision.get("operator_status") == "APPROVED"
        ),
        "execution_outcome_failed": bool(outcome_status == "EXECUTION_FAILED"),
        "alignment_count_gte_2": bool(isinstance(alignment_count, int) and alignment_count >= 2),
        "auto_lane_active": bool(auto_lane_state == "AUTO_LANE_ACTIVE"),
    }


def _failed_reasons(latest_decision: dict[str, Any] | None, checks: dict[str, bool]) -> list[str]:
    if not isinstance(latest_decision, dict):
        return ["no_latest_decision"]
    reasons: list[str] = []
    if not checks["suggestion_retry_recommended"]:
        reasons.append("suggestion_not_retry_recommended")
    if not checks["policy_verdict_auto_allowed"]:
        reasons.append("policy_verdict_not_auto_allowed")
    if not checks["policy_safe_lane_supervised_retry"]:
        reasons.append("policy_safe_lane_not_supervised_retry")
    if not checks["confidence_high"]:
        reasons.append("confidence_band_not_high")
    if not checks["latest_decision_approved"]:
        reasons.append("latest_decision_not_approved")
    if not checks["execution_outcome_failed"]:
        reasons.append("execution_outcome_not_failed")
    if not checks["alignment_count_gte_2"]:
        reasons.append("trust_alignment_count_below_threshold")
    if not checks["auto_lane_active"]:
        reasons.append("auto_lane_frozen")
    return reasons or ["insufficient_eligibility_evidence"]


def _summary(verdict: str, reasons: list[str]) -> str:
    if verdict == ELIGIBLE:
        return "eligible because all required conditions are satisfied"
    if not reasons:
        return "blocked because insufficient eligibility evidence is available"
    labels = [FAILED_REASON_LABELS.get(reason, reason.replace("_", " ")) for reason in reasons]
    if len(labels) == 1:
        return f"blocked because {labels[0]}"
    return "blocked because " + ", ".join(labels[:-1]) + " and " + labels[-1]


def derive_auto_lane_review(
    latest_decision: dict[str, Any] | None,
    policy_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    checks = _check_map(latest_decision, policy_payload)
    reasons = _failed_reasons(latest_decision, checks)
    verdict = ELIGIBLE if all(checks.values()) else BLOCKED
    return {
        "decision_id": latest_decision.get("decision_id") if isinstance(latest_decision, dict) else None,
        "trace_id": latest_decision.get("trace_id") if isinstance(latest_decision, dict) else None,
        "candidate_lane": CANDIDATE_LANE,
        "effective_lane_state": (
            policy_payload.get("auto_lane_state")
            if isinstance(policy_payload, dict) and policy_payload.get("auto_lane_state")
            else "AUTO_LANE_FROZEN"
        ),
        "eligibility_verdict": verdict,
        "reasons": [] if verdict == ELIGIBLE else reasons,
        "checks": checks,
        "summary": _summary(verdict, reasons if verdict == BLOCKED else []),
    }
