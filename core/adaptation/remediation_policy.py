"""AG-20: Remediation policy — hard budget ceilings for the adaptive loop.

These constants are CLC-owned and must not be changed by downstream code.
All ceiling values must be validated before any adaptation action executes.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Hard ceilings — set by CLC, not configurable at runtime
# ---------------------------------------------------------------------------
MAX_RETRY: int = 1
MAX_FALLBACK: int = 1
MAX_ADAPTATION_DEPTH: int = 2

_DESTRUCTIVE_ACTIONS: frozenset[str] = frozenset({
    "delete", "purge", "wipe", "kill", "force_push",
    "drop", "rm_rf", "hard_reset", "quarantine_and_delete",
})

_ALLOWED_ADAPTATION_ACTIONS: frozenset[str] = frozenset({
    "stop", "retry", "safe_fallback", "escalate",
})


def remediation_allowed(
    action: str,
    retry_count: int = 0,
    fallback_count: int = 0,
    adaptation_depth: int = 0,
) -> str:
    """Return ALLOW | BLOCK | ESCALATE for a proposed remediation action.

    Args:
        action:           Proposed action (stop, retry, safe_fallback, escalate).
        retry_count:      Number of retries already consumed for this run.
        fallback_count:   Number of fallbacks already consumed for this run.
        adaptation_depth: Current adaptation depth for this run.

    Returns:
        "ALLOW" | "BLOCK" | "ESCALATE"
    """
    action_lower = action.strip().lower()

    # Destructive → always BLOCK
    if action_lower in _DESTRUCTIVE_ACTIONS:
        return "BLOCK"

    # Unknown action → ESCALATE
    if action_lower not in _ALLOWED_ADAPTATION_ACTIONS:
        return "ESCALATE"

    # STOP is always safe
    if action_lower == "stop":
        return "ALLOW"

    # ESCALATE action → always forward to operator
    if action_lower == "escalate":
        return "ALLOW"

    # Depth budget
    if adaptation_depth >= MAX_ADAPTATION_DEPTH:
        return "ESCALATE"

    # Retry budget
    if action_lower == "retry" and retry_count >= MAX_RETRY:
        return "BLOCK"

    # Fallback budget
    if action_lower == "safe_fallback" and fallback_count >= MAX_FALLBACK:
        return "BLOCK"

    return "ALLOW"
