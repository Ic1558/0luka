from __future__ import annotations

import json
from typing import Any

from tools.ops.control_plane_persistence import (
    DecisionPersistenceError,
    append_decision_event,
)


EXECUTABLE_ACTIONS = {
    "REVIEW_PROOF": "REVIEW_PROOF",
    "QUARANTINE": "QUARANTINE",
    "ESCALATE": "ESCALATE",
}

INTENT_BY_ACTION = {
    "REVIEW_PROOF": "control.review_proof",
    "QUARANTINE": "control.quarantine",
    "ESCALATE": "control.escalate",
}


class ExecutionBridgeError(RuntimeError):
    pass


def _submit_task(task: dict[str, Any], *, task_id: str) -> dict[str, Any]:
    from core.submit import SubmitError, submit_task

    try:
        return submit_task(task, task_id=task_id)
    except SubmitError as exc:
        raise ExecutionBridgeError(f"handoff_failed:{exc}") from exc


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ExecutionBridgeError(f"invalid_{field}")
    return value.strip()


def _require_evidence_refs(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ExecutionBridgeError("invalid_evidence_refs")
    refs: list[str] = []
    for item in value:
        refs.append(_require_text(item, "evidence_ref"))
    return refs


def build_execution_request(decision: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(decision, dict):
        raise ExecutionBridgeError("invalid_decision")

    operator_status = _require_text(decision.get("operator_status"), "operator_status")
    if operator_status != "APPROVED":
        raise ExecutionBridgeError("latest_decision_not_approved")

    proposed_action = _require_text(decision.get("proposed_action"), "proposed_action")
    if proposed_action == "NO_ACTION":
        raise ExecutionBridgeError("no_action_not_executable")
    requested_action = EXECUTABLE_ACTIONS.get(proposed_action)
    if requested_action is None:
        raise ExecutionBridgeError("unsupported_proposed_action")

    return {
        "decision_id": _require_text(decision.get("decision_id"), "decision_id"),
        "trace_id": _require_text(decision.get("trace_id"), "trace_id"),
        "ts_utc": _require_text(decision.get("ts_utc"), "ts_utc"),
        "requested_action": requested_action,
        "evidence_refs": _require_evidence_refs(decision.get("evidence_refs")),
        "source": "mission_control_approved_decision",
    }


def _build_execution_task(request: dict[str, Any]) -> tuple[dict[str, Any], str]:
    requested_action = _require_text(request.get("requested_action"), "requested_action")
    intent = INTENT_BY_ACTION.get(requested_action)
    if intent is None:
        raise ExecutionBridgeError("unsupported_requested_action")

    decision_id = _require_text(request.get("decision_id"), "decision_id")
    trace_id = _require_text(request.get("trace_id"), "trace_id")
    ts_utc = _require_text(request.get("ts_utc"), "ts_utc")
    evidence_refs = _require_evidence_refs(request.get("evidence_refs"))
    task_id = f"decision_exec_{decision_id}"
    payload_json = json.dumps(request, sort_keys=True)

    task = {
        "schema_version": "clec.v1",
        "task_id": task_id,
        "ts_utc": ts_utc,
        "author": "mission_control",
        "call_sign": "[MissionControl]",
        "root": "${ROOT}",
        "intent": intent,
        "trace_id": trace_id,
        "verify": [],
        "ops": [
            {
                "op_id": "op1",
                "type": "write_text",
                "target_path": f"runtime/state/execution_requests/{decision_id}.json",
                "content": payload_json,
            }
        ],
    }
    return task, task_id


def handoff_approved_decision(
    decision: dict[str, Any],
    *,
    observability_root,
) -> dict[str, Any]:
    request = build_execution_request(decision)
    task, task_id = _build_execution_task(request)
    receipt = _submit_task(task, task_id=task_id)

    try:
        append_decision_event(
            observability_root,
            {
                "event": "EXECUTION_HANDOFF_ACCEPTED",
                "decision_id": decision.get("decision_id"),
                "trace_id": decision.get("trace_id"),
                "ts_utc": decision.get("ts_utc"),
                "signal_received": decision.get("signal_received"),
                "proposed_action": decision.get("proposed_action"),
                "evidence_refs": decision.get("evidence_refs"),
                "operator_status": decision.get("operator_status"),
                "operator_note": decision.get("operator_note"),
            },
        )
    except DecisionPersistenceError as exc:
        raise ExecutionBridgeError(str(exc)) from exc

    return {
        "ok": True,
        "bridge_status": "HANDOFF_ACCEPTED",
        "decision_id": request["decision_id"],
        "trace_id": request["trace_id"],
        "requested_action": request["requested_action"],
        "task_id": receipt.get("task_id"),
        "inbox_path": receipt.get("inbox_path"),
    }
