"""AG-20: Adaptive router — orchestrates the remediation loop.

Entry point: route_adaptation()

Flow:
  1. Call choose_next_action() to decide action
  2. Gate via remediation_allowed()
  3. Persist via adaptation_store
  4. Return action + gate verdict

Pure orchestration — no IO side effects beyond the store.
"""
from __future__ import annotations

from typing import Any

from core.adaptation.adaptation_engine import choose_next_action
from core.adaptation.remediation_policy import remediation_allowed
from core.adaptation.adaptation_store import append_adaptation, write_latest


def route_adaptation(
    verification_result: dict[str, Any],
    execution_context: dict[str, Any],
    prior_adaptations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Route to the next bounded adaptation action.

    Args:
        verification_result: Must contain {"status": "SUCCESS"|"FAILED"|"PARTIAL"}.
        execution_context:   Must contain {"run_id": str}.
          Optional: retry_count, fallback_count, adaptation_depth.
        prior_adaptations:   Recent adaptation log entries for budget counting.

    Returns:
        Dict with keys: action, gate_verdict, adaptation_id, run_id.

    Gate verdicts:
        ALLOW   — action approved, proceed.
        BLOCK   — budget exceeded or destructive, do not execute.
        ESCALATE — unknown action or depth ceiling reached.
    """
    prior = prior_adaptations or []

    # Step 1: choose action
    action = choose_next_action(
        verification_result=verification_result,
        execution_context=execution_context,
        prior_adaptations=prior,
    )

    # Step 2: gate
    retry_count = sum(
        1 for a in prior
        if str(a.get("action") or "").lower() == "retry"
        and str(a.get("run_id") or "") == str(execution_context.get("run_id") or "")
    )
    fallback_count = sum(
        1 for a in prior
        if str(a.get("action") or "").lower() == "safe_fallback"
        and str(a.get("run_id") or "") == str(execution_context.get("run_id") or "")
    )
    adaptation_depth = retry_count + fallback_count

    gate_verdict = remediation_allowed(
        action=action,
        retry_count=retry_count,
        fallback_count=fallback_count,
        adaptation_depth=adaptation_depth,
    )

    # Step 3: persist
    record: dict[str, Any] = {
        "run_id": str(execution_context.get("run_id") or ""),
        "action": action,
        "gate_verdict": gate_verdict,
        "verification_status": str(verification_result.get("status") or ""),
        "retry_count": retry_count,
        "fallback_count": fallback_count,
        "adaptation_depth": adaptation_depth,
    }
    record = append_adaptation(record)
    write_latest(record)

    return record
