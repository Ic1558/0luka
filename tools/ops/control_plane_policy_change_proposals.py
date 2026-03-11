from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PROPOSAL_STATUSES = {
    "PROPOSED",
    "UNDER_REVIEW",
    "REJECTED",
    "APPROVED_FOR_IMPLEMENTATION",
}

POLICY_COMPONENTS = {
    "auto_retry_threshold": 0.70,
}


class PolicyProposalError(RuntimeError):
    pass


def _proposal_log_path(observability_root: str | Path) -> Path:
    return Path(observability_root) / "logs" / "policy_change_proposals.jsonl"


def _ensure_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyProposalError(f"invalid_{field}")
    return value.strip()


def _ensure_iso_utc_z(value: Any, field: str) -> str:
    text = _ensure_non_empty_string(value, field)
    if "T" not in text or not text.endswith("Z"):
        raise PolicyProposalError(f"invalid_{field}")
    return text


def _normalize_note(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PolicyProposalError("invalid_operator_note")
    return value


def _coerce_numeric(value: Any, field: str) -> float:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError as exc:
            raise PolicyProposalError(f"invalid_{field}") from exc
    if not isinstance(value, (int, float)):
        raise PolicyProposalError(f"invalid_{field}")
    return round(float(value), 2)


def _ensure_enum(value: Any, field: str, allowed: set[str]) -> str:
    text = _ensure_non_empty_string(value, field)
    if text not in allowed:
        raise PolicyProposalError(f"invalid_{field}")
    return text


def make_proposal_id(*, created_at: str, policy_component: str, proposed_value: float) -> str:
    digest = hashlib.sha256(
        f"{created_at}|{policy_component}|{proposed_value:.2f}".encode("utf-8")
    ).hexdigest()[:16]
    return f"proposal_{digest}"


def _validate_record(record: dict[str, Any]) -> dict[str, Any]:
    created_at = _ensure_iso_utc_z(record.get("created_at"), "created_at")
    policy_component = _ensure_enum(record.get("policy_component"), "policy_component", set(POLICY_COMPONENTS))
    current_value = _coerce_numeric(record.get("current_value"), "current_value")
    proposed_value = _coerce_numeric(record.get("proposed_value"), "proposed_value")
    evidence_summary = _ensure_non_empty_string(record.get("evidence_summary"), "evidence_summary")
    simulation_reference = _ensure_non_empty_string(record.get("simulation_reference"), "simulation_reference")
    status = _ensure_enum(record.get("status"), "status", PROPOSAL_STATUSES)
    operator_note = _normalize_note(record.get("operator_note"))
    proposal_id = record.get("proposal_id")
    expected_id = make_proposal_id(
        created_at=created_at,
        policy_component=policy_component,
        proposed_value=proposed_value,
    )
    if proposal_id is None:
        proposal_id = expected_id
    proposal_id = _ensure_non_empty_string(proposal_id, "proposal_id")
    if proposal_id != expected_id:
        raise PolicyProposalError("invalid_proposal_id")
    return {
        "proposal_id": proposal_id,
        "created_at": created_at,
        "policy_component": policy_component,
        "current_value": current_value,
        "proposed_value": proposed_value,
        "evidence_summary": evidence_summary,
        "simulation_reference": simulation_reference,
        "status": status,
        "operator_note": operator_note,
    }


def _append_record(observability_root: str | Path, record: dict[str, Any]) -> None:
    path = _proposal_log_path(observability_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def create_policy_change_proposal(
    observability_root: str | Path,
    *,
    created_at: str,
    policy_component: str,
    proposed_value: float | str,
    evidence_summary: str,
    simulation_reference: str,
    operator_note: str | None = None,
) -> dict[str, Any]:
    component = _ensure_enum(policy_component, "policy_component", set(POLICY_COMPONENTS))
    record = _validate_record(
        {
            "created_at": created_at,
            "policy_component": component,
            "current_value": POLICY_COMPONENTS[component],
            "proposed_value": proposed_value,
            "evidence_summary": evidence_summary,
            "simulation_reference": simulation_reference,
            "status": "PROPOSED",
            "operator_note": operator_note,
        }
    )
    _append_record(observability_root, record)
    return record


def list_policy_change_proposals(observability_root: str | Path, *, limit: int = 50) -> list[dict[str, Any]]:
    if not isinstance(limit, int) or limit < 1:
        raise PolicyProposalError("invalid_limit")
    bounded_limit = min(limit, 200)
    path = _proposal_log_path(observability_root)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PolicyProposalError("unreadable_policy_change_proposals") from exc
    items: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PolicyProposalError("unreadable_policy_change_proposals") from exc
        if not isinstance(payload, dict):
            raise PolicyProposalError("invalid_policy_change_proposals")
        items.append(_validate_record(payload))
    if len(items) <= bounded_limit:
        return items
    return items[-bounded_limit:]


def get_policy_change_proposal(observability_root: str | Path, proposal_id: str) -> dict[str, Any] | None:
    target = _ensure_non_empty_string(proposal_id, "proposal_id")
    for item in reversed(list_policy_change_proposals(observability_root, limit=200)):
        if item["proposal_id"] == target:
            return item
    return None
