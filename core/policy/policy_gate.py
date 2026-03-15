"""AG-18/AG-19: Policy gate — evaluates decisions, plans, and steps.

Returns ALLOW | BLOCK | ESCALATE for each surface.

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


def policy_verdict_with_learning_signal(
    decision: "Union[DecisionRecord, dict]",
    prior_decisions: "list[dict] | None" = None,
) -> dict:
    """Like policy_verdict() but returns verdict + AG-21 learning metadata.

    Extra keys: learning_signal (bool), pattern_tag (str).
    Does NOT change verdict logic — metadata only.
    """
    verdict = policy_verdict(decision, prior_decisions)
    if isinstance(decision, DecisionRecord):
        action = decision.action
        confidence = float(decision.confidence)
    else:
        action = str(decision.get("action") or "")
        confidence = float(decision.get("confidence") or 0.0)

    # Derive learning signal and pattern tag from verdict + action
    learning_signal = verdict in ("BLOCK", "ESCALATE")
    if verdict == "BLOCK":
        pattern_tag = f"policy_block:{action.lower()}"
    elif verdict == "ESCALATE" and confidence < CONFIDENCE_THRESHOLD:
        pattern_tag = "low_confidence_escalate"
    elif verdict == "ESCALATE":
        pattern_tag = f"unknown_action_escalate:{action.lower()}"
    else:
        pattern_tag = ""

    return {
        "verdict": verdict,
        "learning_signal": learning_signal,
        "pattern_tag": pattern_tag,
    }


# ---------------------------------------------------------------------------
# AG-19 plan-level and step-level gates
# ---------------------------------------------------------------------------

_ALLOWED_STEP_ACTIONS: frozenset[str] = frozenset({"verify_artifacts", "retry_task"})
_MAX_PLAN_RETRY_STEPS: int = 1


def step_allowed(step: dict) -> str:
    """Return ALLOW, BLOCK, or ESCALATE for a single plan step.

    Rules:
      - unknown/disallowed action → ESCALATE
      - destructive action → BLOCK
      - verify_artifacts → ALLOW
      - retry_task → ALLOW (caller responsible for retry-count check)
    """
    action = str(step.get("action") or "").strip().lower()
    if not action:
        return "ESCALATE"
    if action in {a.lower() for a in DESTRUCTIVE_ACTIONS}:
        return "BLOCK"
    if action in _ALLOWED_STEP_ACTIONS:
        return "ALLOW"
    return "ESCALATE"


def plan_allowed(
    plan: dict,
    prior_plans: list[dict] | None = None,
) -> str:
    """Return ALLOW, BLOCK, or ESCALATE for an entire plan.

    Rules:
      - multi-step plan with branching (>2 unique action types) → ESCALATE
      - any step that is BLOCK or ESCALATE → propagate worst verdict
      - retry_task count > MAX_PLAN_RETRY_STEPS for same run → BLOCK
      - empty/no-op plan → ALLOW
    """
    steps: list[dict] = plan.get("steps") or []

    if not steps:
        return "ALLOW"

    # Check individual steps
    verdicts = [step_allowed(s) for s in steps]
    if "BLOCK" in verdicts:
        return "BLOCK"

    # AG-22/AG-23: consult promoted policy registry before ESCALATE short-circuit
    # Only ACTIVE policies are enforced; DEPRECATED/REVOKED/SUPERSEDED/EXPIRED skipped.
    # (fail-open: if registry unavailable, fall through to normal verdict)
    try:
        from core.policy.policy_lifecycle import list_active_policies, INACTIVE_STATUSES
        active_policies = list_active_policies()
        action_types = {str(s.get("action") or "").lower() for s in steps}
        for policy in active_policies:
            rule = str(policy.get("rule") or "").lower()
            if "deny_delete_repo" in rule and "delete_repo" in action_types:
                return "BLOCK"
    except Exception:
        pass  # registry unavailable — proceed without promoted policy check

    if "ESCALATE" in verdicts:
        return "ESCALATE"

    # Check retry count across prior plans for the same run
    run_id = str(plan.get("run_id") or "")
    retry_steps_in_plan = sum(
        1 for s in steps if str(s.get("action") or "").lower() == "retry_task"
    )
    prior_retry_steps = 0
    if prior_plans and run_id:
        for pp in prior_plans:
            if str(pp.get("run_id") or "") == run_id:
                for s in (pp.get("steps") or []):
                    if str(s.get("action") or "").lower() == "retry_task":
                        prior_retry_steps += 1

    if prior_retry_steps + retry_steps_in_plan > _MAX_PLAN_RETRY_STEPS:
        return "BLOCK"

    return "ALLOW"
