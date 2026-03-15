"""AG-22: Policy promoter — promotes approved candidates into the policy registry.

Flow:
  operator calls promote(candidate, operator_id)
    → promotion_verifier.verify_candidate()   # confidence + approval_state check
    → policy_registry.register_policy()       # atomic upsert
    → policy_registry.append_activation_log() # audit trail

Safety invariants:
  - No auto-promotion: operator_id required, approval_state must be APPROVED
  - Atomic registry write via policy_registry.save_registry()
  - PENDING candidates are rejected
  - Returns result dict — never raises
"""
from __future__ import annotations

import time
from typing import Any

from core.policy.promotion_verifier import verify_candidate
from core.policy.policy_registry import register_policy, append_activation_log


def promote(candidate: dict[str, Any], operator_id: str) -> dict[str, Any]:
    """Promote an approved policy candidate into the runtime registry.

    Args:
        candidate:   Policy candidate dict.  Must have approval_state="APPROVED",
                     confidence>=0.8, and all required fields.
        operator_id: Identity of the operator authorising promotion.
                     Non-empty string required — promotion is rejected without it.

    Returns:
        dict with keys: ok (bool), policy_id (str|None), reason (str).
    """
    if not operator_id or not str(operator_id).strip():
        return {"ok": False, "policy_id": None, "reason": "operator_id required"}

    ok, reason = verify_candidate(candidate)
    if not ok:
        return {"ok": False, "policy_id": None, "reason": reason}

    policy_id = candidate["candidate_id"]
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    policy_record: dict[str, Any] = {
        "policy_id": policy_id,
        "source_candidate_id": candidate.get("candidate_id", policy_id),
        "pattern_id": candidate["pattern_id"],
        "rule": candidate["suggested_policy"],
        "safety_risk": candidate.get("safety_risk", "low"),
        "confidence": float(candidate.get("confidence") or 0.0),
        "source": "learning",
        "activated_at": now,
        "activated_by": operator_id,
    }

    try:
        register_policy(policy_id, policy_record)
        append_activation_log({
            "ts": now,
            "candidate_id": policy_id,
            "policy_id": policy_id,
            "operator_id": operator_id,
            "status": "ACTIVATED",
        })
    except RuntimeError as exc:
        return {"ok": False, "policy_id": None, "reason": str(exc)}

    return {"ok": True, "policy_id": policy_id, "reason": "promoted"}
