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

RETRYABLE_OUTCOMES = {"EXECUTION_FAILED", "EXECUTION_UNKNOWN"}


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
    return build_execution_request_with_action(decision, requested_action=None, source="mission_control_approved_decision")


def build_execution_request_with_action(
    decision: dict[str, Any],
    *,
    requested_action: str | None,
    source: str,
) -> dict[str, Any]:
    if not isinstance(decision, dict):
        raise ExecutionBridgeError("invalid_decision")

    operator_status = _require_text(decision.get("operator_status"), "operator_status")
    if operator_status != "APPROVED":
        raise ExecutionBridgeError("latest_decision_not_approved")

    proposed_action = _require_text(decision.get("proposed_action"), "proposed_action")
    action = requested_action or proposed_action
    if action == "NO_ACTION":
        raise ExecutionBridgeError("no_action_not_executable")
    mapped_action = EXECUTABLE_ACTIONS.get(action)
    if mapped_action is None:
        raise ExecutionBridgeError("unsupported_proposed_action")

    return {
        "decision_id": _require_text(decision.get("decision_id"), "decision_id"),
        "trace_id": _require_text(decision.get("trace_id"), "trace_id"),
        "ts_utc": _require_text(decision.get("ts_utc"), "ts_utc"),
        "requested_action": mapped_action,
        "evidence_refs": _require_evidence_refs(decision.get("evidence_refs")),
        "source": source,
    }


def _build_execution_task(request: dict[str, Any], *, task_suffix: str = "") -> tuple[dict[str, Any], str]:
    requested_action = _require_text(request.get("requested_action"), "requested_action")
    intent = INTENT_BY_ACTION.get(requested_action)
    if intent is None:
        raise ExecutionBridgeError("unsupported_requested_action")

    decision_id = _require_text(request.get("decision_id"), "decision_id")
    trace_id = _require_text(request.get("trace_id"), "trace_id")
    ts_utc = _require_text(request.get("ts_utc"), "ts_utc")
    evidence_refs = _require_evidence_refs(request.get("evidence_refs"))
    task_id = f"decision_exec_{decision_id}{task_suffix}"
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


def _handoff_request(
    decision: dict[str, Any],
    *,
    observability_root,
    requested_action: str | None,
    source: str,
    task_suffix: str,
    ledger_event: str,
    response_key: str,
    response_body: dict[str, Any],
) -> dict[str, Any]:
    request = build_execution_request_with_action(
        decision,
        requested_action=requested_action,
        source=source,
    )
    task, task_id = _build_execution_task(request, task_suffix=task_suffix)
    receipt = _submit_task(task, task_id=task_id)

    try:
        append_decision_event(
            observability_root,
            {
                "event": ledger_event,
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
        response_key: {
            **response_body,
            "decision_id": request["decision_id"],
            "trace_id": request["trace_id"],
            "requested_action": request["requested_action"],
            "task_id": receipt.get("task_id"),
            "inbox_path": receipt.get("inbox_path"),
        },
    }


def handoff_approved_decision(
    decision: dict[str, Any],
    *,
    observability_root,
) -> dict[str, Any]:
    payload = _handoff_request(
        decision,
        observability_root=observability_root,
        requested_action=None,
        source="mission_control_approved_decision",
        task_suffix="",
        ledger_event="EXECUTION_HANDOFF_ACCEPTED",
        response_key="handoff",
        response_body={"bridge_status": "HANDOFF_ACCEPTED"},
    )["handoff"]
    return {
        "ok": True,
        "bridge_status": payload["bridge_status"],
        "decision_id": payload["decision_id"],
        "trace_id": payload["trace_id"],
        "requested_action": payload["requested_action"],
        "task_id": payload["task_id"],
        "inbox_path": payload["inbox_path"],
    }


def retry_approved_decision(
    decision: dict[str, Any],
    *,
    observability_root,
    retry_count: int,
) -> dict[str, Any]:
    if retry_count < 1:
        raise ExecutionBridgeError("invalid_retry_count")
    return _handoff_request(
        decision,
        observability_root=observability_root,
        requested_action=None,
        source="mission_control_retry",
        task_suffix=f"_retry_{retry_count}",
        ledger_event="EXECUTION_RETRY_REQUESTED",
        response_key="retry",
        response_body={"retry_count": retry_count},
    )


def escalate_approved_decision(
    decision: dict[str, Any],
    *,
    observability_root,
    escalation_count: int,
    reason: str,
) -> dict[str, Any]:
    if escalation_count < 1:
        raise ExecutionBridgeError("invalid_escalation_count")
    return _handoff_request(
        decision,
        observability_root=observability_root,
        requested_action="ESCALATE",
        source="mission_control_escalation",
        task_suffix=f"_escalate_{escalation_count}",
        ledger_event="EXECUTION_ESCALATION_REQUESTED",
        response_key="escalation",
        response_body={"reason": reason, "escalation_count": escalation_count},
    )
