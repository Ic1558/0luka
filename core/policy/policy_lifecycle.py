"""AG-23: Policy Lifecycle & Governance.

Manages the full lifecycle of promoted policies:
  ACTIVE → DEPRECATED → REVOKED
  ACTIVE → SUPERSEDED (when replaced by a newer policy)
  ACTIVE → EXPIRED    (when TTL elapses)

All transitions are operator-triggered or TTL-driven.
No transition is automatic except TTL expiry, which only marks status —
it does NOT delete records.

Status values:
  ACTIVE      — enforced by policy_gate
  DEPRECATED  — visible but NOT enforced (soft removal; no BLOCK)
  REVOKED     — hard-removed from enforcement; kept for audit trail
  SUPERSEDED  — replaced by superseded_by policy_id; not enforced
  EXPIRED     — TTL elapsed; not enforced

All status changes are appended to policy_activation_log.jsonl.
"""
from __future__ import annotations

import time
from typing import Any

from core.policy.policy_registry import (
    load_registry,
    save_registry,
    append_activation_log,
)

# Statuses that policy_gate must ignore
INACTIVE_STATUSES: frozenset[str] = frozenset({
    "DEPRECATED", "REVOKED", "SUPERSEDED", "EXPIRED",
})

# Default TTL for active policies (seconds).  0 = no expiry.
DEFAULT_TTL_SECONDS: int = 0


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

def revoke_policy(policy_id: str, operator_id: str, reason: str = "") -> dict[str, Any]:
    """Hard-revoke a policy: marks status=REVOKED, not enforced.

    The record remains in the registry for audit purposes but policy_gate
    will skip it.  Returns {ok, policy_id, reason}.
    """
    if not operator_id or not str(operator_id).strip():
        return {"ok": False, "policy_id": policy_id, "reason": "operator_id required"}

    reg = load_registry()
    if policy_id not in reg:
        return {"ok": False, "policy_id": policy_id, "reason": "policy not found"}

    reg[policy_id]["status"] = "REVOKED"
    reg[policy_id]["revoked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    reg[policy_id]["revoked_by"] = operator_id
    if reason:
        reg[policy_id]["revoke_reason"] = reason
    save_registry(reg)

    append_activation_log({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "policy_id": policy_id,
        "operator_id": operator_id,
        "status": "REVOKED",
        "reason": reason,
    })
    return {"ok": True, "policy_id": policy_id, "reason": "revoked"}


def deprecate_policy(policy_id: str, operator_id: str, reason: str = "") -> dict[str, Any]:
    """Soft-deprecate a policy: marks status=DEPRECATED.

    Deprecated policies are not enforced by policy_gate but remain visible
    in the registry for documentation/history.
    """
    if not operator_id or not str(operator_id).strip():
        return {"ok": False, "policy_id": policy_id, "reason": "operator_id required"}

    reg = load_registry()
    if policy_id not in reg:
        return {"ok": False, "policy_id": policy_id, "reason": "policy not found"}

    reg[policy_id]["status"] = "DEPRECATED"
    reg[policy_id]["deprecated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    reg[policy_id]["deprecated_by"] = operator_id
    if reason:
        reg[policy_id]["deprecate_reason"] = reason
    save_registry(reg)

    append_activation_log({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "policy_id": policy_id,
        "operator_id": operator_id,
        "status": "DEPRECATED",
        "reason": reason,
    })
    return {"ok": True, "policy_id": policy_id, "reason": "deprecated"}


def supersede_policy(
    old_policy_id: str,
    new_policy_id: str,
    operator_id: str,
) -> dict[str, Any]:
    """Mark old_policy as SUPERSEDED by new_policy_id.

    Both policies must exist in the registry.  The old policy's status is
    set to SUPERSEDED and a superseded_by pointer is written.
    """
    if not operator_id or not str(operator_id).strip():
        return {"ok": False, "policy_id": old_policy_id, "reason": "operator_id required"}

    reg = load_registry()
    if old_policy_id not in reg:
        return {"ok": False, "policy_id": old_policy_id, "reason": f"policy {old_policy_id!r} not found"}
    if new_policy_id not in reg:
        return {"ok": False, "policy_id": old_policy_id, "reason": f"new policy {new_policy_id!r} not found"}

    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    reg[old_policy_id]["status"] = "SUPERSEDED"
    reg[old_policy_id]["superseded_by"] = new_policy_id
    reg[old_policy_id]["superseded_at"] = now
    reg[old_policy_id]["superseded_by_operator"] = operator_id
    save_registry(reg)

    append_activation_log({
        "ts": now,
        "policy_id": old_policy_id,
        "operator_id": operator_id,
        "status": "SUPERSEDED",
        "superseded_by": new_policy_id,
    })
    return {"ok": True, "policy_id": old_policy_id, "reason": f"superseded by {new_policy_id}"}


# ---------------------------------------------------------------------------
# TTL expiry
# ---------------------------------------------------------------------------

def expire_stale_policies(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> list[str]:
    """Scan registry for ACTIVE policies older than ttl_seconds; mark EXPIRED.

    Only runs expiry if ttl_seconds > 0.  Returns list of expired policy_ids.
    Safe to call repeatedly (idempotent for already-expired policies).
    """
    if ttl_seconds <= 0:
        return []

    reg = load_registry()
    if not reg:
        return []

    now = time.time()
    expired_ids: list[str] = []

    for policy_id, record in reg.items():
        if record.get("status", "ACTIVE") != "ACTIVE":
            continue
        activated_at_str = str(record.get("activated_at") or "")
        if not activated_at_str:
            continue
        try:
            import calendar
            activated_ts = float(calendar.timegm(
                time.strptime(activated_at_str, "%Y-%m-%dT%H:%M:%SZ")
            ))
        except (ValueError, OverflowError):
            continue
        if now - activated_ts > ttl_seconds:
            expired_ids.append(policy_id)

    if not expired_ids:
        return []

    now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for policy_id in expired_ids:
        reg[policy_id]["status"] = "EXPIRED"
        reg[policy_id]["expired_at"] = now_str
    save_registry(reg)

    for policy_id in expired_ids:
        append_activation_log({
            "ts": now_str,
            "policy_id": policy_id,
            "status": "EXPIRED",
            "ttl_seconds": ttl_seconds,
        })

    return expired_ids


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def list_active_policies() -> list[dict[str, Any]]:
    """Return only ACTIVE policies (safe for policy_gate consumption)."""
    return [
        p for p in load_registry().values()
        if p.get("status", "ACTIVE") not in INACTIVE_STATUSES
    ]


def list_policies_by_status(status: str) -> list[dict[str, Any]]:
    """Return all policies with the given status."""
    status_upper = status.upper()
    return [
        p for p in load_registry().values()
        if p.get("status", "ACTIVE").upper() == status_upper
    ]
