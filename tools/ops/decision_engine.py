from __future__ import annotations

import logging
from typing import Any

from tools.ops.control_plane_persistence import (
    DecisionPersistenceError,
    read_latest_decision,
    write_pending_decision,
)


SIGNAL_TO_ACTION = {
    "COMPLETE": "NO_ACTION",
    "NOMINAL": "NO_ACTION",
    "MISSING_PROOF": "REVIEW_PROOF",
    "INCONSISTENT": "QUARANTINE",
    "DRIFT_DETECTED": "QUARANTINE",
}


def _read_ok(payload: Any) -> bool | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("ok")
    return value if isinstance(value, bool) else None


def _read_drift_count(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("drift_count")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def classify_once(
    operator_status: Any,
    runtime_status: Any,
    policy_drift: Any,
) -> str | None:
    operator_ok = _read_ok(operator_status)
    runtime_ok = _read_ok(runtime_status)
    drift_count = _read_drift_count(policy_drift)

    if operator_ok is None or runtime_ok is None or drift_count is None:
        return None
    if operator_ok is False:
        return "drift_detected"
    if runtime_ok is False:
        return "drift_detected"
    if drift_count > 0:
        return "drift_detected"
    return "nominal"


def map_signal_to_action(signal_received: Any) -> str:
    if not isinstance(signal_received, str):
        return "ESCALATE"
    return SIGNAL_TO_ACTION.get(signal_received.strip().upper(), "ESCALATE")


def generate_proposal_once(
    *,
    trace_id: str,
    signal_received: str,
    evidence_refs: Any,
    ts_utc: str,
    runtime_root: Any,
    observability_root: Any,
) -> dict[str, Any] | None:
    if not isinstance(trace_id, str) or not trace_id.strip():
        raise DecisionPersistenceError("invalid_trace_id")
    if not isinstance(signal_received, str) or not signal_received.strip():
        raise DecisionPersistenceError("invalid_signal_received")
    if not isinstance(evidence_refs, list) or not evidence_refs or any(
        not isinstance(item, str) or not item.strip() for item in evidence_refs
    ):
        raise DecisionPersistenceError("invalid_evidence_refs")
    if not isinstance(ts_utc, str) or "T" not in ts_utc or not ts_utc.endswith("Z"):
        raise DecisionPersistenceError("invalid_ts_utc")

    proposed_action = map_signal_to_action(signal_received)
    if proposed_action == "NO_ACTION":
        return None

    latest = read_latest_decision(runtime_root)
    if latest is not None and latest.get("operator_status") == "PENDING":
        logging.warning("pending decision exists; skipping proposal generation")
        return None

    proposal = {
        "trace_id": trace_id,
        "ts_utc": ts_utc,
        "signal_received": signal_received,
        "proposed_action": proposed_action,
        "evidence_refs": evidence_refs,
        "operator_status": "PENDING",
        "operator_note": None,
    }
    return write_pending_decision(proposal, runtime_root, observability_root)
