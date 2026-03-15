"""AG-28: Recovery policy — gates every recovery action before execution.

Hard ceilings (CLC-owned, not runtime-configurable):
  MAX_RECOVERY_ATTEMPTS = 1
"""
from __future__ import annotations

from typing import Any

MAX_RECOVERY_ATTEMPTS: int = 1

_UNSAFE_RECOVERY_ACTIONS: frozenset[str] = frozenset({
    "git_reset", "git_gc", "git_prune", "git_repack",
    "shell_exec", "config_rewrite", "launchd_edit", "plist_edit",
})

_ALLOWED_RECOVERY_ACTIONS: frozenset[str] = frozenset({
    "retry_once", "recheck_artifacts", "refresh_runtime_state",
    "request_operator", "stop",
})


def evaluate_recovery_policy(
    failure_context: dict[str, Any],
    recovery_action: dict[str, Any],
    prior_recoveries: list[dict[str, Any]] | None = None,
) -> str:
    """Evaluate whether a recovery action is allowed.

    Args:
        failure_context: Dict from verifier with failure type and flags.
        recovery_action: Dict from recovery_engine with recovery_action key.
        prior_recoveries: Recent recovery log entries (for budget counting).

    Returns:
        "ALLOW" | "BLOCK" | "ESCALATE" | "STOP"
    """
    action = str(recovery_action.get("recovery_action") or "").lower()
    run_id = str(failure_context.get("run_id") or "")
    prior = prior_recoveries or []

    # Unsafe action → BLOCK
    if action in _UNSAFE_RECOVERY_ACTIONS:
        return "BLOCK"

    # Unknown action → ESCALATE
    if action not in _ALLOWED_RECOVERY_ACTIONS:
        return "ESCALATE"

    # STOP and REQUEST_OPERATOR are always allowed
    if action in ("stop", "request_operator"):
        return "ALLOW"

    # Protected zone failure → no automatic recovery
    if failure_context.get("protected_zone_related"):
        return "ESCALATE"

    # Topology sensitive failure → STOP
    if failure_context.get("topology_sensitive"):
        return "STOP"

    # Process conflict → STOP
    if failure_context.get("process_conflict"):
        return "STOP"

    # Recovery budget: MAX_RECOVERY_ATTEMPTS per run
    prior_attempts = sum(
        1 for r in prior
        if str(r.get("run_id") or "") == run_id
        and str(r.get("recovery_action") or "").lower() not in ("stop", "request_operator")
    )
    if prior_attempts >= MAX_RECOVERY_ATTEMPTS:
        return "ESCALATE"

    # Repeated failure pattern from verifier → escalate
    if failure_context.get("repeated_failure"):
        return "ESCALATE"

    return "ALLOW"
