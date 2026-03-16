"""AG-32: Drift Governance — operator-governed finding lifecycle.

Defines the lifecycle for AG-31 drift findings:
  OPEN → ACCEPTED | DISMISSED | ESCALATED → RESOLVED

All write operations require a non-empty operator_id.
No automatic acceptance, no automatic baseline mutation, no repair.

Usage:
    from core.audit.drift_governance import accept_finding, escalate_finding
    result = accept_finding("finding-001", operator_id="boss", note="known naming drift")
"""
from __future__ import annotations

from typing import Any

# Valid finding lifecycle states
VALID_STATES: frozenset[str] = frozenset({
    "OPEN",
    "ACCEPTED",
    "DISMISSED",
    "ESCALATED",
    "RESOLVED",
})

# Allowed state transitions (from_state → set of allowed to_states)
# OPEN can go to any non-OPEN state.
# ACCEPTED/DISMISSED/ESCALATED can be re-evaluated → RESOLVED or back to OPEN.
# RESOLVED is terminal (can be re-opened if drift re-emerges).
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "OPEN":      frozenset({"ACCEPTED", "DISMISSED", "ESCALATED"}),
    "ACCEPTED":  frozenset({"DISMISSED", "ESCALATED", "RESOLVED", "OPEN"}),
    "DISMISSED": frozenset({"OPEN", "ESCALATED", "RESOLVED"}),
    "ESCALATED": frozenset({"RESOLVED", "ACCEPTED", "DISMISSED", "OPEN"}),
    "RESOLVED":  frozenset({"OPEN"}),   # re-open if drift re-emerges
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_operator(operator_id: str) -> None:
    if not operator_id or not operator_id.strip():
        raise ValueError("operator_id is required for all governance write actions")


def _current_status(finding_id: str) -> str:
    """Return the current status of a finding, defaulting to OPEN."""
    from core.audit.drift_governance_store import get_finding_status
    record = get_finding_status(finding_id)
    if record is None:
        return "OPEN"
    return str(record.get("status", "OPEN"))


def _validate_transition(finding_id: str, target_status: str) -> None:
    """Raise ValueError if the transition is not allowed."""
    current = _current_status(finding_id)
    allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
    if target_status not in allowed:
        raise ValueError(
            f"Transition from {current!r} → {target_status!r} is not allowed "
            f"for finding '{finding_id}'. Allowed from {current!r}: {sorted(allowed)}"
        )


def _govern(
    finding_id: str,
    new_status: str,
    operator_id: str,
    note: str | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Common path: validate, record, return result."""
    _require_operator(operator_id)
    operator_id = operator_id.strip()
    _validate_transition(finding_id, new_status)

    from core.audit.drift_governance_store import set_finding_status
    return set_finding_status(finding_id, new_status, operator_id, note=note, extra=extra)


# ---------------------------------------------------------------------------
# Public operator actions
# ---------------------------------------------------------------------------

def accept_finding(
    finding_id: str,
    operator_id: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Mark a finding as ACCEPTED (governance-accepted, not yet in baseline code).

    Use when: the drift is known and accepted as-is at governance level.
    Does NOT modify audit_baseline.py. Use promote_to_baseline() to propose that.
    """
    return _govern(finding_id, "ACCEPTED", operator_id, note)


def dismiss_finding(
    finding_id: str,
    operator_id: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Mark a finding as DISMISSED (false positive or audit noise).

    History is preserved. The finding remains in the governance log.
    """
    return _govern(finding_id, "DISMISSED", operator_id, note)


def escalate_finding(
    finding_id: str,
    operator_id: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Mark a finding as ESCALATED (real drift, requires patch/PR/incident).

    ESCALATED findings should be tracked as inputs to future repair planning.
    """
    return _govern(finding_id, "ESCALATED", operator_id, note)


def resolve_finding(
    finding_id: str,
    operator_id: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Mark a finding as RESOLVED (drift has been addressed or is no longer relevant).

    Evidence from the finding is preserved in the governance log.
    """
    return _govern(finding_id, "RESOLVED", operator_id, note)


def promote_to_baseline(
    finding_id: str,
    operator_id: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Propose promoting a finding's accepted drift into audit_baseline.py.

    Does NOT modify audit_baseline.py automatically.
    Creates a PENDING_REVIEW record in drift_baseline_proposals.jsonl.
    A human must review the proposal and manually update audit_baseline.py.

    The finding status is set to ACCEPTED (if not already) with a note
    that a baseline promotion is pending.
    """
    _require_operator(operator_id)
    operator_id = operator_id.strip()

    import uuid
    import time
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    proposal_id = uuid.uuid4().hex[:10]

    proposal = {
        "ts": ts,
        "proposal_id": proposal_id,
        "finding_id": finding_id,
        "operator_id": operator_id,
        "note": note or "",
        "proposal": "Promote accepted drift into core/audit/audit_baseline.py",
        "status": "PENDING_REVIEW",
        "instruction": (
            "Manual action required: review this finding and add an entry to "
            "KNOWN_ACCEPTED_DRIFT in core/audit/audit_baseline.py if appropriate. "
            "This file is NOT modified automatically."
        ),
    }

    from core.audit.drift_governance_store import append_baseline_proposal
    append_baseline_proposal(proposal)

    # Also update finding status to ACCEPTED (idempotent — validate transition)
    current = _current_status(finding_id)
    status_result: dict[str, Any]
    if current != "ACCEPTED":
        from core.audit.drift_governance_store import set_finding_status
        set_finding_status(
            finding_id, "ACCEPTED", operator_id,
            note=f"baseline promotion proposed (proposal_id={proposal_id})",
            extra={"proposal_id": proposal_id},
        )

    return {
        "ok": True,
        "finding_id": finding_id,
        "proposal_id": proposal_id,
        "status": "PENDING_REVIEW",
        "message": (
            "Baseline promotion proposal created. "
            "Review drift_baseline_proposals.jsonl and manually update audit_baseline.py."
        ),
    }


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def list_open_findings() -> list[dict[str, Any]]:
    """Return all findings that have status OPEN (or no recorded status yet)."""
    from core.audit.drift_governance_store import list_finding_status
    return list_finding_status(status_filter="OPEN")


def list_governed_findings(status: str | None = None) -> list[dict[str, Any]]:
    """Return all governed findings, optionally filtered by status."""
    from core.audit.drift_governance_store import list_finding_status
    return list_finding_status(status_filter=status)
