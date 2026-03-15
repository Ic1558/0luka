"""AG-20: Adaptation engine — chooses the next bounded safe action after verification.

Pure function: choose_next_action() has no IO side effects.
All state reads are passed in as arguments.

Possible outputs: STOP | RETRY | SAFE_FALLBACK | ESCALATE
"""
from __future__ import annotations

from typing import Any

from core.adaptation.remediation_policy import MAX_ADAPTATION_DEPTH, MAX_FALLBACK, MAX_RETRY


def _count_prior(prior_adaptations: list[dict[str, Any]], action: str, run_id: str) -> int:
    """Count how many times action was used for run_id in prior adaptations."""
    return sum(
        1 for a in prior_adaptations
        if str(a.get("action") or "").lower() == action.lower()
        and str(a.get("run_id") or "") == run_id
    )


def choose_next_action(
    verification_result: dict[str, Any],
    execution_context: dict[str, Any],
    prior_adaptations: list[dict[str, Any]] | None = None,
) -> str:
    """Decide the next bounded adaptation action based on verification outcome.

    Args:
        verification_result: Dict with at least {"status": "SUCCESS"|"FAILED"|"PARTIAL"}.
        execution_context:   Dict with at least {"run_id": str}.
          Optional keys: retry_count, fallback_count, adaptation_depth.
        prior_adaptations:   Recent adaptation records for budget counting.

    Returns:
        "STOP" | "RETRY" | "SAFE_FALLBACK" | "ESCALATE"

    Decision rules (in order):
    1. SUCCESS → STOP
    2. adaptation_depth >= MAX_ADAPTATION_DEPTH → ESCALATE
    3. FAILED + retry budget available → RETRY
    4. PARTIAL + fallback budget available → SAFE_FALLBACK
    5. any remaining → ESCALATE
    """
    status = str(verification_result.get("status") or "").upper()
    run_id = str(execution_context.get("run_id") or "")
    prior = prior_adaptations or []

    # Rule 1: success → done
    if status == "SUCCESS":
        return "STOP"

    # Count prior actions for this run
    prior_retries = _count_prior(prior, "retry", run_id)
    prior_fallbacks = _count_prior(prior, "safe_fallback", run_id)
    # Depth = total adaptive actions taken (retry + fallback)
    adaptation_depth = prior_retries + prior_fallbacks

    # Rule 2: depth ceiling
    if adaptation_depth >= MAX_ADAPTATION_DEPTH:
        return "ESCALATE"

    # Rule 3: FAILED → retry if budget allows
    if status == "FAILED" and prior_retries < MAX_RETRY:
        return "RETRY"

    # Rule 4: PARTIAL → fallback if budget allows
    if status == "PARTIAL" and prior_fallbacks < MAX_FALLBACK:
        return "SAFE_FALLBACK"

    # Rule 5: all other cases → escalate
    return "ESCALATE"
