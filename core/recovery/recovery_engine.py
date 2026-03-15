"""AG-28: Recovery engine — selects bounded recovery action from approved playbook.

Pure function: select_recovery_action() has no IO side effects.
All decision logic is deterministic given the failure_context.

Allowed outputs: RETRY_ONCE | RECHECK_ARTIFACTS | REFRESH_RUNTIME_STATE | REQUEST_OPERATOR | STOP
"""
from __future__ import annotations

from typing import Any

# Approved recovery actions — no dynamic expansion permitted
ALLOWED_RECOVERY_ACTIONS: frozenset[str] = frozenset({
    "RETRY_ONCE",
    "RECHECK_ARTIFACTS",
    "REFRESH_RUNTIME_STATE",
    "REQUEST_OPERATOR",
    "STOP",
})

# Failure types that must never auto-recover
_NEVER_AUTO_RECOVER: frozenset[str] = frozenset({
    "protected_zone_violation",
    "emergency_stop_triggered",
    "topology_lockdown",
    "process_concurrency_conflict",
    "policy_block",
    "unknown",
})


def select_recovery_action(failure_context: dict[str, Any]) -> dict[str, Any]:
    """Select a recovery action from the approved playbook.

    Args:
        failure_context: Dict with keys:
          failure_type         (str)  — type of failure (e.g. verification_failed)
          recoverable          (bool) — whether verifier says it may be recoverable
          requires_operator    (bool) — whether operator involvement is required
          protected_zone_related (bool) — whether failure involves protected paths
          topology_sensitive   (bool) — whether failure involves topology state
          status               (str)  — SUCCESS | FAILED | PARTIAL from verifier

    Returns:
        Dict with: recovery_action, reason, confidence, requires_operator
    """
    failure_type = str(failure_context.get("failure_type") or "unknown").lower()
    recoverable = bool(failure_context.get("recoverable", False))
    requires_operator = bool(failure_context.get("requires_operator", False))
    protected_zone = bool(failure_context.get("protected_zone_related", False))
    topology_sensitive = bool(failure_context.get("topology_sensitive", False))

    # Protected zone violations → never auto-recover
    if protected_zone:
        return _action("REQUEST_OPERATOR", "protected_zone_related_failure", 0.95, requires_operator=True)

    # Topology unstable → stop
    if topology_sensitive:
        return _action("STOP", "topology_sensitive_failure", 0.9, requires_operator=False)

    # Operator required (from verifier or failure type)
    if requires_operator or failure_type in _NEVER_AUTO_RECOVER:
        return _action("REQUEST_OPERATOR", f"requires_operator_for_{failure_type}", 0.85, requires_operator=True)

    # Recoverable failure type mapping
    if failure_type in ("verification_failed", "execution_failed") and recoverable:
        return _action("RETRY_ONCE", "transient_execution_failure", 0.7, requires_operator=False)

    if failure_type in ("missing_artifact", "artifact_mismatch"):
        return _action("RECHECK_ARTIFACTS", "artifact_surface_incomplete", 0.75, requires_operator=False)

    if failure_type in ("runtime_state_stale", "cache_stale", "state_inconsistent"):
        return _action("REFRESH_RUNTIME_STATE", "runtime_read_model_stale", 0.8, requires_operator=False)

    # Unrecoverable or unknown → STOP (safe default, not REQUEST_OPERATOR to avoid infinite loop)
    return _action("STOP", f"no_approved_recovery_for_{failure_type}", 0.5, requires_operator=False)


def _action(action: str, reason: str, confidence: float, *, requires_operator: bool) -> dict[str, Any]:
    return {
        "recovery_action": action,
        "reason": reason,
        "confidence": confidence,
        "requires_operator": requires_operator,
    }
