from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROPOSED_ACTIONS = {
    "ESCALATE",
    "QUARANTINE",
    "REVIEW_PROOF",
    "NO_ACTION",
}

OPERATOR_STATUSES = {
    "PENDING",
    "APPROVED",
    "REJECTED",
    "EXPIRED",
    "SUPERSEDED",
}

LEDGER_EVENTS = {
    "PROPOSAL_CREATED",
    "OPERATOR_APPROVED",
    "OPERATOR_REJECTED",
    "PROPOSAL_SUPERSEDED",
    "EXECUTION_HANDOFF_ACCEPTED",
    "EXECUTION_RETRY_REQUESTED",
    "EXECUTION_ESCALATION_REQUESTED",
    "SUGGESTION_ACCEPTED",
    "SUGGESTION_IGNORED",
    "SUGGESTION_OVERRIDDEN",
}

SUGGESTION_VALUES = {
    "RETRY_RECOMMENDED",
    "ESCALATION_RECOMMENDED",
    "NO_ACTION_RECOMMENDED",
}

CONFIDENCE_BANDS = {
    "HIGH",
    "MEDIUM",
    "LOW",
}

OPERATOR_ACTIONS = {
    "RETRY_EXECUTION",
    "ESCALATE_ISSUE",
    "IGNORE_SUGGESTION",
}

SUGGESTION_ALIGNMENT = {
    "MATCHED_SUGGESTION",
    "IGNORED_SUGGESTION",
    "OVERRIDDEN",
}

RESOLUTION_EVENT_BY_STATUS = {
    "APPROVED": "OPERATOR_APPROVED",
    "REJECTED": "OPERATOR_REJECTED",
}


class DecisionPersistenceError(RuntimeError):
    pass


def _latest_path(runtime_root: str | Path) -> Path:
    return Path(runtime_root) / "state" / "decision_latest.json"


def _ledger_path(observability_root: str | Path) -> Path:
    return Path(observability_root) / "logs" / "decision_log.jsonl"


def _ensure_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionPersistenceError(f"invalid_{field}")
    return value


def _ensure_iso_utc_z(value: Any, field: str) -> str:
    text = _ensure_non_empty_string(value, field)
    if "T" not in text or not text.endswith("Z"):
        raise DecisionPersistenceError(f"invalid_{field}")
    return text


def _ensure_enum(value: Any, field: str, allowed: set[str]) -> str:
    text = _ensure_non_empty_string(value, field)
    if text not in allowed:
        raise DecisionPersistenceError(f"invalid_{field}")
    return text


def _ensure_evidence_refs(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise DecisionPersistenceError("invalid_evidence_refs")
    refs: list[str] = []
    for item in value:
        refs.append(_ensure_non_empty_string(item, "evidence_ref"))
    return refs


def _normalize_operator_note(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DecisionPersistenceError("invalid_operator_note")
    return value


def _optional_enum(value: Any, field: str, allowed: set[str]) -> str | None:
    if value is None:
        return None
    return _ensure_enum(value, field, allowed)


def make_decision_id(*, trace_id: str, ts_utc: str, signal_received: str, proposed_action: str) -> str:
    digest = hashlib.sha256(
        f"{trace_id}|{ts_utc}|{signal_received}|{proposed_action}".encode("utf-8")
    ).hexdigest()[:16]
    return f"decision_{digest}"


def _validated_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    trace_id = _ensure_non_empty_string(proposal.get("trace_id"), "trace_id")
    ts_utc = _ensure_iso_utc_z(proposal.get("ts_utc"), "ts_utc")
    signal_received = _ensure_non_empty_string(proposal.get("signal_received"), "signal_received")
    proposed_action = _ensure_enum(proposal.get("proposed_action"), "proposed_action", PROPOSED_ACTIONS)
    evidence_refs = _ensure_evidence_refs(proposal.get("evidence_refs"))
    operator_status = _ensure_enum(proposal.get("operator_status"), "operator_status", OPERATOR_STATUSES)
    operator_note = _normalize_operator_note(proposal.get("operator_note"))
    decision_id = proposal.get("decision_id")
    expected_decision_id = make_decision_id(
        trace_id=trace_id,
        ts_utc=ts_utc,
        signal_received=signal_received,
        proposed_action=proposed_action,
    )
    if decision_id is None:
        decision_id = expected_decision_id
    decision_id = _ensure_non_empty_string(decision_id, "decision_id")
    if decision_id != expected_decision_id:
        raise DecisionPersistenceError("invalid_decision_id")
    return {
        "decision_id": decision_id,
        "trace_id": trace_id,
        "ts_utc": ts_utc,
        "signal_received": signal_received,
        "proposed_action": proposed_action,
        "evidence_refs": evidence_refs,
        "operator_status": operator_status,
        "operator_note": operator_note,
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DecisionPersistenceError(f"unreadable_{path.name}") from exc
    if not isinstance(payload, dict):
        raise DecisionPersistenceError(f"invalid_{path.name}")
    return payload


def _read_existing_latest(runtime_root: str | Path) -> dict[str, Any] | None:
    path = _latest_path(runtime_root)
    if not path.exists():
        return None
    payload = _read_json(path)
    return _validated_proposal(payload)


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _append_ledger_event(observability_root: str | Path, payload: dict[str, Any]) -> None:
    event_name = _ensure_enum(payload.get("event"), "event", LEDGER_EVENTS)
    record = {
        "event": event_name,
        "decision_id": _ensure_non_empty_string(payload.get("decision_id"), "decision_id"),
        "trace_id": _ensure_non_empty_string(payload.get("trace_id"), "trace_id"),
        "ts_utc": _ensure_iso_utc_z(payload.get("ts_utc"), "ts_utc"),
        "operator_status": _ensure_enum(payload.get("operator_status"), "operator_status", OPERATOR_STATUSES),
        "proposed_action": _ensure_enum(payload.get("proposed_action"), "proposed_action", PROPOSED_ACTIONS),
        "evidence_refs": _ensure_evidence_refs(payload.get("evidence_refs")),
    }
    optional_fields = {
        "operator_note": _normalize_operator_note(payload.get("operator_note")),
        "suggestion": _optional_enum(payload.get("suggestion"), "suggestion", SUGGESTION_VALUES),
        "confidence_band": _optional_enum(payload.get("confidence_band"), "confidence_band", CONFIDENCE_BANDS),
        "operator_action": _optional_enum(payload.get("operator_action"), "operator_action", OPERATOR_ACTIONS),
        "alignment": _optional_enum(payload.get("alignment"), "alignment", SUGGESTION_ALIGNMENT),
    }
    for key, value in optional_fields.items():
        if value is not None:
            record[key] = value
    path = _ledger_path(observability_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def read_latest_decision(runtime_root: str | Path) -> dict[str, Any] | None:
    return _read_existing_latest(runtime_root)


def read_decision_history(observability_root: str | Path, limit: int = 50) -> list[dict[str, Any]]:
    if not isinstance(limit, int):
        raise DecisionPersistenceError("invalid_limit")
    if limit < 1:
        raise DecisionPersistenceError("invalid_limit")
    bounded_limit = min(limit, 200)
    path = _ledger_path(observability_root)
    if not path.exists():
        return []

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise DecisionPersistenceError("unreadable_decision_log.jsonl") from exc

    items: list[dict[str, Any]] = []
    for raw_line in lines:
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise DecisionPersistenceError("unreadable_decision_log.jsonl") from exc
        if not isinstance(payload, dict):
            raise DecisionPersistenceError("invalid_decision_log.jsonl")
        event_name = _ensure_enum(payload.get("event"), "event", LEDGER_EVENTS)
        items.append(
            {
                "event": event_name,
                "decision_id": _ensure_non_empty_string(payload.get("decision_id"), "decision_id"),
                "trace_id": _ensure_non_empty_string(payload.get("trace_id"), "trace_id"),
                "ts_utc": _ensure_iso_utc_z(payload.get("ts_utc"), "ts_utc"),
                "operator_status": _ensure_enum(payload.get("operator_status"), "operator_status", OPERATOR_STATUSES),
                "proposed_action": _ensure_enum(payload.get("proposed_action"), "proposed_action", PROPOSED_ACTIONS),
                "evidence_refs": _ensure_evidence_refs(payload.get("evidence_refs")),
                "operator_note": _normalize_operator_note(payload.get("operator_note")),
                "suggestion": _optional_enum(payload.get("suggestion"), "suggestion", SUGGESTION_VALUES),
                "confidence_band": _optional_enum(payload.get("confidence_band"), "confidence_band", CONFIDENCE_BANDS),
                "operator_action": _optional_enum(payload.get("operator_action"), "operator_action", OPERATOR_ACTIONS),
                "alignment": _optional_enum(payload.get("alignment"), "alignment", SUGGESTION_ALIGNMENT),
            }
        )

    if len(items) <= bounded_limit:
        return items
    return items[-bounded_limit:]


def append_decision_event(observability_root: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    validated = _validated_proposal(payload)
    _append_ledger_event(
        observability_root,
        {
            "event": payload.get("event"),
            **validated,
        },
    )
    return validated


def append_suggestion_feedback(
    observability_root: str | Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    validated = _validated_proposal(payload)
    event = _ensure_enum(payload.get("event"), "event", {"SUGGESTION_ACCEPTED", "SUGGESTION_IGNORED", "SUGGESTION_OVERRIDDEN"})
    suggestion = _ensure_enum(payload.get("suggestion"), "suggestion", SUGGESTION_VALUES)
    confidence_band = _ensure_enum(payload.get("confidence_band"), "confidence_band", CONFIDENCE_BANDS)
    operator_action = _ensure_enum(payload.get("operator_action"), "operator_action", OPERATOR_ACTIONS)
    alignment = _ensure_enum(payload.get("alignment"), "alignment", SUGGESTION_ALIGNMENT)
    _append_ledger_event(
        observability_root,
        {
            "event": event,
            **validated,
            "suggestion": suggestion,
            "confidence_band": confidence_band,
            "operator_action": operator_action,
            "alignment": alignment,
        },
    )
    return {
        **validated,
        "event": event,
        "suggestion": suggestion,
        "confidence_band": confidence_band,
        "operator_action": operator_action,
        "alignment": alignment,
    }


def read_suggestion_feedback(observability_root: str | Path, decision_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    rows = read_decision_history(observability_root, limit=limit)
    items = [
        row for row in rows
        if row.get("event") in {"SUGGESTION_ACCEPTED", "SUGGESTION_IGNORED", "SUGGESTION_OVERRIDDEN"}
    ]
    if decision_id is not None:
        items = [row for row in items if row.get("decision_id") == decision_id]
    return items


def write_pending_decision(
    proposal: dict[str, Any],
    runtime_root: str | Path,
    observability_root: str | Path,
) -> dict[str, Any]:
    validated = _validated_proposal(proposal)
    if validated["operator_status"] != "PENDING":
        raise DecisionPersistenceError("pending_status_required")

    existing = _read_existing_latest(runtime_root)
    if existing is not None and existing["operator_status"] == "PENDING":
        raise DecisionPersistenceError("pending_decision_exists")

    _write_json_atomic(_latest_path(runtime_root), validated)
    _append_ledger_event(
        observability_root,
        {
            "event": "PROPOSAL_CREATED",
            **validated,
        },
    )
    return validated


def record_operator_decision(
    decision_id: str,
    operator_status: str,
    runtime_root: str | Path,
    observability_root: str | Path,
    operator_note: str | None = None,
) -> dict[str, Any]:
    expected_id = _ensure_non_empty_string(decision_id, "decision_id")
    status = _ensure_enum(operator_status, "operator_status", set(RESOLUTION_EVENT_BY_STATUS))
    note = _normalize_operator_note(operator_note)

    existing = _read_existing_latest(runtime_root)
    if existing is None:
        raise DecisionPersistenceError("latest_decision_missing")
    if existing["decision_id"] != expected_id:
        raise DecisionPersistenceError("decision_id_mismatch")

    updated = dict(existing)
    updated["operator_status"] = status
    updated["operator_note"] = note

    _write_json_atomic(_latest_path(runtime_root), updated)
    _append_ledger_event(
        observability_root,
        {
            "event": RESOLUTION_EVENT_BY_STATUS[status],
            **updated,
        },
    )
    return updated
