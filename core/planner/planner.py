"""AG-19: Planner — converts a DecisionRecord into a bounded execution plan.

Rules:
  - nominal / NO_ACTION  → no-op plan (empty steps)
  - REVIEW_PROOF         → [verify_artifacts]
  - QUARANTINE           → [verify_artifacts, retry_task]
  - retry                → [retry_task]
  - anything else        → empty plan (policy gate will gate at step level)

The planner is a PURE function. It does NOT:
  - write to filesystem
  - enqueue anything
  - execute steps
  - call shell or git
"""
from __future__ import annotations

import hashlib
import time
from typing import Any

from core.decision.models import DecisionRecord

_ACTION_TO_STEPS: dict[str, list[dict[str, str]]] = {
    "no_action": [],
    "nominal":   [],
    "review_proof": [{"action": "verify_artifacts"}],
    "quarantine":   [{"action": "verify_artifacts"}, {"action": "retry_task"}],
    "retry":        [{"action": "retry_task"}],
}

_SAFE_STEP_ACTIONS: frozenset[str] = frozenset({"verify_artifacts", "retry_task"})


def create_plan(
    decision: DecisionRecord,
    run_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert a classified decision into a bounded execution plan.

    Args:
        decision:  The classified DecisionRecord from decision_engine.
        run_state: Optional runtime context dict (e.g. {"run_id": "..."}).

    Returns:
        Plan dict with keys: plan_id, run_id, decision_id, created_at,
        steps, status, reason.
    """
    ts_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    run_id = str((run_state or {}).get("run_id") or decision.source_run_id)

    action_lower = decision.action.strip().lower()
    steps = _ACTION_TO_STEPS.get(action_lower, [])

    # No-op if nothing to execute
    status = "NO_OP" if not steps else "CREATED"

    raw = f"{run_id}|{decision.decision_id}|{ts_utc}"
    plan_id = "plan_" + hashlib.sha256(raw.encode()).hexdigest()[:12]

    return {
        "plan_id": plan_id,
        "run_id": run_id,
        "decision_id": decision.decision_id,
        "created_at": ts_utc,
        "steps": steps,
        "status": status,
        "reason": decision.classification,
    }
