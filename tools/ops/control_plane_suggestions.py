from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.ops.control_plane_persistence import DecisionPersistenceError, read_latest_decision
from tools.ops.execution_outcome_reconciler import reconcile_execution_outcome


SUGGESTION_RETRY = "RETRY_RECOMMENDED"
SUGGESTION_ESCALATE = "ESCALATION_RECOMMENDED"
SUGGESTION_NO_ACTION = "NO_ACTION_RECOMMENDED"


def derive_suggestion(
    latest_decision: dict[str, Any] | None,
    execution: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(latest_decision, dict):
        return {
            "decision_id": None,
            "trace_id": None,
            "decision_state": None,
            "execution_outcome": None,
            "suggestion": SUGGESTION_NO_ACTION,
            "reason": "no_latest_decision",
        }

    decision_state = latest_decision.get("operator_status")
    execution_outcome = execution.get("outcome_status") if isinstance(execution, dict) else None
    payload = {
        "decision_id": latest_decision.get("decision_id"),
        "trace_id": latest_decision.get("trace_id"),
        "decision_state": decision_state,
        "execution_outcome": execution_outcome,
    }

    if decision_state != "APPROVED":
        return {
            **payload,
            "suggestion": SUGGESTION_NO_ACTION,
            "reason": "latest_decision_not_approved",
        }
    if execution_outcome == "EXECUTION_FAILED":
        return {
            **payload,
            "suggestion": SUGGESTION_RETRY,
            "reason": "execution_failed_after_approved_decision",
        }
    if execution_outcome == "EXECUTION_UNKNOWN":
        return {
            **payload,
            "suggestion": SUGGESTION_ESCALATE,
            "reason": "execution_outcome_unknown_after_approved_decision",
        }
    if execution_outcome == "EXECUTION_SUCCEEDED":
        return {
            **payload,
            "suggestion": SUGGESTION_NO_ACTION,
            "reason": "execution_succeeded",
        }
    if execution_outcome == "HANDOFF_ONLY":
        return {
            **payload,
            "suggestion": SUGGESTION_NO_ACTION,
            "reason": "waiting_for_confirmed_execution_outcome",
        }
    return {
        **payload,
        "suggestion": SUGGESTION_NO_ACTION,
        "reason": "no_reconciled_execution_outcome",
    }


def load_latest_suggestion(
    *,
    runtime_root: Path,
    observability_root: Path,
    repo_root: Path,
) -> dict[str, Any]:
    try:
        latest = read_latest_decision(runtime_root)
    except DecisionPersistenceError:
        latest = None
    execution = reconcile_execution_outcome(
        latest,
        repo_root=repo_root,
        observability_root=observability_root,
    )
    return derive_suggestion(latest, execution)
