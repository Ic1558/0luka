from __future__ import annotations

from typing import Any


CANDIDATE_LANE = "SUPERVISED_RETRY"
ELIGIBLE = "ELIGIBLE"
BLOCKED = "BLOCKED"
BASELINE_ALIGNMENT_THRESHOLD = 2
BASELINE_CONFIDENCE_REQUIREMENT = "HIGH"
ALLOWED_ALIGNMENT_THRESHOLDS = {1, 2, 3}
ALLOWED_CONFIDENCE_REQUIREMENTS = {"HIGH", "MEDIUM"}

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


def _normalize_alignment_threshold(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("invalid_alignment_threshold")
    if value not in ALLOWED_ALIGNMENT_THRESHOLDS:
        raise ValueError("invalid_alignment_threshold")
    return value


def _normalize_confidence_requirement(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("invalid_confidence_requirement")
    normalized = value.strip().upper()
    if normalized == "RELAXED_TO_MEDIUM":
        normalized = "MEDIUM"
    if normalized not in ALLOWED_CONFIDENCE_REQUIREMENTS:
        raise ValueError("invalid_confidence_requirement")
    return normalized


def _check_map(
    latest_decision: dict[str, Any] | None,
    policy_payload: dict[str, Any] | None,
    *,
    alignment_threshold: int = BASELINE_ALIGNMENT_THRESHOLD,
    confidence_requirement: str = BASELINE_CONFIDENCE_REQUIREMENT,
    simulate_policy_gate: bool = False,
) -> dict[str, bool]:
    execution = latest_decision.get("execution") if isinstance(latest_decision, dict) else None
    outcome_status = execution.get("outcome_status") if isinstance(execution, dict) else None
    alignment_count = policy_payload.get("alignment_count") if isinstance(policy_payload, dict) else None
    auto_lane_state = policy_payload.get("auto_lane_state") if isinstance(policy_payload, dict) else None
    normalized_alignment_threshold = _normalize_alignment_threshold(alignment_threshold)
    normalized_confidence_requirement = _normalize_confidence_requirement(confidence_requirement)
    suggestion_retry_recommended = bool(
        isinstance(policy_payload, dict) and policy_payload.get("suggestion") == "RETRY_RECOMMENDED"
    )
    policy_safe_lane_supervised_retry = bool(
        isinstance(policy_payload, dict) and policy_payload.get("policy_safe_lane") == CANDIDATE_LANE
    )
    confidence_requirement_met = bool(
        isinstance(policy_payload, dict)
        and (
            policy_payload.get("confidence_band") == "HIGH"
            or (
                normalized_confidence_requirement == "MEDIUM"
                and policy_payload.get("confidence_band") == "MEDIUM"
            )
        )
    )
    alignment_threshold_met = bool(
        isinstance(alignment_count, int) and alignment_count >= normalized_alignment_threshold
    )
    policy_verdict_auto_allowed = bool(
        isinstance(policy_payload, dict) and policy_payload.get("policy_verdict") == "AUTO_ALLOWED"
    )
    if simulate_policy_gate:
        policy_verdict_auto_allowed = bool(
            suggestion_retry_recommended
            and policy_safe_lane_supervised_retry
            and confidence_requirement_met
            and alignment_threshold_met
        )
    return {
        "suggestion_retry_recommended": suggestion_retry_recommended,
        "policy_verdict_auto_allowed": policy_verdict_auto_allowed,
        "policy_safe_lane_supervised_retry": policy_safe_lane_supervised_retry,
        "confidence_high": confidence_requirement_met,
        "latest_decision_approved": bool(
            isinstance(latest_decision, dict) and latest_decision.get("operator_status") == "APPROVED"
        ),
        "execution_outcome_failed": bool(outcome_status == "EXECUTION_FAILED"),
        "alignment_count_gte_2": alignment_threshold_met,
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
    *,
    alignment_threshold: int = BASELINE_ALIGNMENT_THRESHOLD,
    confidence_requirement: str = BASELINE_CONFIDENCE_REQUIREMENT,
    simulate_policy_gate: bool = False,
) -> dict[str, Any]:
    checks = _check_map(
        latest_decision,
        policy_payload,
        alignment_threshold=alignment_threshold,
        confidence_requirement=confidence_requirement,
        simulate_policy_gate=simulate_policy_gate,
    )
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
