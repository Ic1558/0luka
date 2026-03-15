"""AG-18: Policy gate — evaluates a DecisionRecord and returns ALLOW | BLOCK | ESCALATE.

Rules (evaluated in order):
1. Destructive actions  → BLOCK
2. Low confidence       → ESCALATE
3. Unknown action       → ESCALATE
4. retry (≤1 prior)     → ALLOW  (>1 prior retry for same run → BLOCK)
5. no_action / nominal  → ALLOW
"""
from __future__ import annotations

from typing import Union

from core.decision.models import DecisionRecord

DESTRUCTIVE_ACTIONS: frozenset[str] = frozenset({
    "delete", "purge", "wipe", "kill", "force_push", "drop", "rm_rf",
    "quarantine_and_delete", "hard_reset",
})

SAFE_TERMINAL_ACTIONS: frozenset[str] = frozenset({
    "no_action", "nominal", "none",
})

CONFIDENCE_THRESHOLD: float = 0.6
MAX_RETRY_COUNT: int = 1


def policy_verdict(
    decision: Union[DecisionRecord, dict],
    prior_decisions: list[dict] | None = None,
) -> str:
    """Return ALLOW, BLOCK, or ESCALATE for the given decision.

    Args:
        decision: A DecisionRecord or plain dict with the same keys.
        prior_decisions: Optional list of recent decision dicts for retry-count check.

    Returns:
        "ALLOW" | "BLOCK" | "ESCALATE"
    """
    if isinstance(decision, DecisionRecord):
        action = decision.action
        confidence = float(decision.confidence)
        source_run_id = decision.source_run_id
    else:
        action = str(decision.get("action") or "")
        confidence = float(decision.get("confidence") or 0.0)
        source_run_id = str(decision.get("source_run_id") or "")

    action_lower = action.strip().lower()

    # Rule 1: destructive → BLOCK
    if action_lower in DESTRUCTIVE_ACTIONS:
        return "BLOCK"

    # Rule 2: low confidence → ESCALATE
    if confidence < CONFIDENCE_THRESHOLD:
        return "ESCALATE"

    # Rule 3: unknown action → ESCALATE
    if not action_lower:
        return "ESCALATE"

    # Rule 4: retry — allowed only once per source run
    if action_lower == "retry":
        prior_retries = 0
        if prior_decisions:
            prior_retries = sum(
                1
                for d in prior_decisions
                if str(d.get("action") or "").lower() == "retry"
                and str(d.get("source_run_id") or "") == source_run_id
            )
        if prior_retries >= MAX_RETRY_COUNT:
            return "BLOCK"
        return "ALLOW"

    # Rule 5: safe terminal actions → ALLOW
    if action_lower in SAFE_TERMINAL_ACTIONS:
        return "ALLOW"

    # Anything else is unknown
    return "ESCALATE"
