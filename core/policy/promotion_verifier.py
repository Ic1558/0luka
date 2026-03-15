"""AG-22: Promotion verifier — gates a policy candidate before it enters the registry.

Rules (evaluated in order):
1. candidate_id present        → required
2. pattern_id present          → required
3. suggested_policy non-empty  → required
4. approval_state == APPROVED  → operator must have explicitly approved
5. confidence >= 0.8           → high-confidence patterns only
6. safety_risk not "high"      → high-risk candidates require manual override path

Returns (ok: bool, reason: str).
"""
from __future__ import annotations

from typing import Any

_MIN_CONFIDENCE: float = 0.8
_BLOCKED_RISK_LEVELS: frozenset[str] = frozenset({"high"})


def verify_candidate(candidate: dict[str, Any]) -> tuple[bool, str]:
    """Verify a candidate dict is safe to promote.

    Args:
        candidate: Policy candidate dict (from learning/policy_candidates.py).

    Returns:
        (True, "ok") on pass, or (False, reason_string) on failure.
    """
    if not candidate.get("candidate_id"):
        return False, "missing candidate_id"

    if not candidate.get("pattern_id"):
        return False, "missing pattern_id"

    if not str(candidate.get("suggested_policy") or "").strip():
        return False, "empty suggested_policy"

    if candidate.get("approval_state") != "APPROVED":
        return False, f"approval_state={candidate.get('approval_state')!r} — must be APPROVED"

    confidence = float(candidate.get("confidence") or 0.0)
    if confidence < _MIN_CONFIDENCE:
        return False, f"confidence={confidence} below threshold {_MIN_CONFIDENCE}"

    risk = str(candidate.get("safety_risk") or "").lower()
    if risk in _BLOCKED_RISK_LEVELS:
        return False, f"safety_risk={risk!r} blocked — requires manual override"

    return True, "ok"
