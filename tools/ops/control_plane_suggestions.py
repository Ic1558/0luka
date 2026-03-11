from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.ops.control_plane_persistence import DecisionPersistenceError, read_latest_decision
from tools.ops.execution_outcome_reconciler import reconcile_execution_outcome


SUGGESTION_RETRY = "RETRY_RECOMMENDED"
SUGGESTION_ESCALATE = "ESCALATION_RECOMMENDED"
SUGGESTION_NO_ACTION = "NO_ACTION_RECOMMENDED"
CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"


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
            "confidence_score": 0.2,
            "confidence_band": CONFIDENCE_LOW,
            "reason": "no_latest_decision",
            "root_cause_hint": "no latest decision available for suggestion analysis",
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
            "confidence_score": 0.35,
            "confidence_band": CONFIDENCE_LOW,
            "reason": "latest_decision_not_approved",
            "root_cause_hint": "latest decision is not in approved state for advisory follow-up",
        }
    if execution_outcome == "EXECUTION_FAILED":
        return {
            **payload,
            "suggestion": SUGGESTION_RETRY,
            "confidence_score": 0.9,
            "confidence_band": CONFIDENCE_HIGH,
            "reason": "execution_failed_after_approved_decision",
            "root_cause_hint": "deterministic execution failure observed after approved handoff",
        }
    if execution_outcome == "EXECUTION_UNKNOWN":
        return {
            **payload,
            "suggestion": SUGGESTION_ESCALATE,
            "confidence_score": 0.65,
            "confidence_band": CONFIDENCE_MEDIUM,
            "reason": "execution_outcome_unknown_after_approved_decision",
            "root_cause_hint": "downstream result not safely reconcilable from current execution surfaces",
        }
    if execution_outcome == "EXECUTION_SUCCEEDED":
        return {
            **payload,
            "suggestion": SUGGESTION_NO_ACTION,
            "confidence_score": 0.95,
            "confidence_band": CONFIDENCE_HIGH,
            "reason": "execution_succeeded",
            "root_cause_hint": "execution completed successfully; no further action suggested",
        }
    if execution_outcome == "HANDOFF_ONLY":
        return {
            **payload,
            "suggestion": SUGGESTION_NO_ACTION,
            "confidence_score": 0.45,
            "confidence_band": CONFIDENCE_LOW,
            "reason": "waiting_for_confirmed_execution_outcome",
            "root_cause_hint": "execution was handed off but no confirmed downstream outcome is available",
        }
    return {
        **payload,
        "suggestion": SUGGESTION_NO_ACTION,
        "confidence_score": 0.3,
        "confidence_band": CONFIDENCE_LOW,
        "reason": "no_reconciled_execution_outcome",
        "root_cause_hint": "no reconciled execution outcome is available from current state surfaces",
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
