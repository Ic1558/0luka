"""AG-30: Outcome router — maps AG-29 effectiveness verdicts to governance recommendations.

Verdict → recommended_action mapping:
  KEEP                  → RETAIN
  REVIEW                → REVIEW_REQUIRED
  ROLLBACK_RECOMMENDED  → ROLLBACK_CANDIDATE
  INCONCLUSIVE          → MONITOR

The router is PURE — no IO, no side effects.
It only computes what the operator should be prompted to do.
All state persistence is handled by outcome_store.
"""
from __future__ import annotations

from typing import Any

# Verdict constants (from AG-29)
_KEEP = "KEEP"
_REVIEW = "REVIEW"
_ROLLBACK_RECOMMENDED = "ROLLBACK_RECOMMENDED"
_INCONCLUSIVE = "INCONCLUSIVE"

# Recommended action constants
RETAIN = "RETAIN"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
ROLLBACK_CANDIDATE = "ROLLBACK_CANDIDATE"
MONITOR = "MONITOR"

# Operator action constants (what operator can execute on a governance record)
ACTION_RETAINED = "RETAINED"
ACTION_ROLLED_BACK = "ROLLED_BACK"
ACTION_QUARANTINED = "QUARANTINED"       # soft — maps to DEPRECATED in lifecycle
ACTION_SUPERSEDED = "SUPERSEDED"         # deferred replacement
ACTION_DISMISSED = "DISMISSED"           # operator consciously ignores recommendation

VALID_OPERATOR_ACTIONS: frozenset[str] = frozenset({
    ACTION_RETAINED, ACTION_ROLLED_BACK, ACTION_QUARANTINED,
    ACTION_SUPERSEDED, ACTION_DISMISSED,
})

_VERDICT_TO_RECOMMENDATION: dict[str, str] = {
    _KEEP: RETAIN,
    _REVIEW: REVIEW_REQUIRED,
    _ROLLBACK_RECOMMENDED: ROLLBACK_CANDIDATE,
    _INCONCLUSIVE: MONITOR,
}


def route_verdict(effectiveness_record: dict[str, Any]) -> dict[str, Any]:
    """Convert an AG-29 effectiveness record into a governance recommendation.

    Args:
        effectiveness_record: Dict from evaluate_policy_effectiveness() / verify_policy_effectiveness().
            Required keys: policy_id, verdict.

    Returns:
        dict with: policy_id, effectiveness_verdict, recommended_action, rationale.
    """
    policy_id = str(effectiveness_record.get("policy_id") or "")
    verdict = str(effectiveness_record.get("verdict") or "").upper()

    recommended_action = _VERDICT_TO_RECOMMENDATION.get(verdict, MONITOR)

    rationale = _build_rationale(effectiveness_record, verdict, recommended_action)

    return {
        "policy_id": policy_id,
        "effectiveness_verdict": verdict,
        "recommended_action": recommended_action,
        "rationale": rationale,
        # pass-through evidence fields for operator context
        "before_failures": effectiveness_record.get("before_failures"),
        "after_failures": effectiveness_record.get("after_failures"),
        "baseline_failure_rate": effectiveness_record.get("baseline_failure_rate"),
        "post_failure_rate": effectiveness_record.get("post_failure_rate"),
        "delta": effectiveness_record.get("delta"),
        "before_count": effectiveness_record.get("before_count"),
        "after_count": effectiveness_record.get("after_count"),
    }


def _build_rationale(record: dict[str, Any], verdict: str, action: str) -> str:
    if verdict == _KEEP:
        delta = record.get("delta")
        if delta is not None:
            return f"failure_rate_improved_by_{abs(float(delta)):.1%} — policy confirmed effective"
        return "policy confirmed effective"
    if verdict == _ROLLBACK_RECOMMENDED:
        delta = record.get("delta")
        if delta is not None:
            return f"failure_rate_worsened_by_{abs(float(delta)):.1%} — revoke or supersede recommended"
        return "post-promotion failure rate increased — revoke or supersede recommended"
    if verdict == _REVIEW:
        return "marginal outcome change — operator review recommended before retention or revocation"
    if verdict == _INCONCLUSIVE:
        after_count = record.get("after_count") or 0
        return f"only {after_count} post-promotion observations — continue monitoring"
    return f"unknown verdict {verdict!r} — defaulting to monitor"
