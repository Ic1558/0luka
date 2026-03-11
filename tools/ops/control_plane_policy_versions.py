from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tools.ops.control_plane_policy_change_proposals import PolicyProposalError


ACTIVE_STATUS = "ACTIVE"
SUPPORTED_COMPONENTS = {"auto_retry_threshold": 0.70}
ROLLBACK_REQUESTED_EVENT = "POLICY_ROLLBACK_REQUESTED"
ROLLED_BACK_EVENT = "POLICY_ROLLED_BACK"


def _version_log_path(observability_root: str | Path) -> Path:
    return Path(observability_root) / "logs" / "policy_versions.jsonl"


def _live_policy_path(runtime_root: str | Path) -> Path:
    return Path(runtime_root) / "state" / "policy_live.json"


def _version_event_log_path(observability_root: str | Path) -> Path:
    return Path(observability_root) / "logs" / "policy_version_events.jsonl"


def _ensure_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolicyProposalError(f"invalid_{field}")
    return value.strip()


def _ensure_iso_utc_z(value: Any, field: str) -> str:
    text = _ensure_non_empty_string(value, field)
    if "T" not in text or not text.endswith("Z"):
        raise PolicyProposalError(f"invalid_{field}")
    return text


def _coerce_numeric(value: Any, field: str) -> float:
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError as exc:
            raise PolicyProposalError(f"invalid_{field}") from exc
    if not isinstance(value, (int, float)):
        raise PolicyProposalError(f"invalid_{field}")
    return round(float(value), 2)


def _ensure_component(value: Any) -> str:
    text = _ensure_non_empty_string(value, "policy_component")
    if text not in SUPPORTED_COMPONENTS:
        raise PolicyProposalError("invalid_policy_component")
    return text


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def make_policy_version_id(
    *,
    deployed_at: str,
    proposal_id: str | None,
    policy_component: str,
    new_value: float,
    rollback_of_version_id: str | None = None,
) -> str:
    proposal_key = proposal_id if proposal_id is not None else "rollback"
    rollback_key = rollback_of_version_id or "direct"
    digest = hashlib.sha256(
        f"{deployed_at}|{proposal_key}|{policy_component}|{new_value:.2f}|{rollback_key}".encode("utf-8")
    ).hexdigest()[:16]
    return f"policy_version_{digest}"


def _validate_version(record: dict[str, Any]) -> dict[str, Any]:
    deployed_at = _ensure_iso_utc_z(record.get("deployed_at"), "deployed_at")
    proposal_raw = record.get("proposal_id")
    proposal_id = None if proposal_raw is None else _ensure_non_empty_string(proposal_raw, "proposal_id")
    policy_component = _ensure_component(record.get("policy_component"))
    previous_value = _coerce_numeric(record.get("previous_value"), "previous_value")
    new_value = _coerce_numeric(record.get("new_value"), "new_value")
    status = _ensure_non_empty_string(record.get("status"), "status")
    rollback_raw = record.get("rollback_of_version_id")
    rollback_of_version_id = None if rollback_raw is None else _ensure_non_empty_string(rollback_raw, "rollback_of_version_id")
    if status != ACTIVE_STATUS:
        raise PolicyProposalError("invalid_status")
    version_id = record.get("policy_version_id")
    expected = make_policy_version_id(
        deployed_at=deployed_at,
        proposal_id=proposal_id,
        policy_component=policy_component,
        new_value=new_value,
        rollback_of_version_id=rollback_of_version_id,
    )
    if version_id is None:
        version_id = expected
    version_id = _ensure_non_empty_string(version_id, "policy_version_id")
    if version_id != expected:
        raise PolicyProposalError("invalid_policy_version_id")
    return {
        "policy_version_id": version_id,
        "deployed_at": deployed_at,
        "proposal_id": proposal_id,
        "policy_component": policy_component,
        "previous_value": previous_value,
        "new_value": new_value,
        "status": status,
        "rollback_of_version_id": rollback_of_version_id,
    }


def _append_version_event(
    observability_root: str | Path,
    *,
    event: str,
    policy_component: str,
    created_at: str,
    from_version_id: str,
    to_version_id: str,
    restored_value: float | str,
    operator_note: str | None = None,
) -> dict[str, Any]:
    if event not in {ROLLBACK_REQUESTED_EVENT, ROLLED_BACK_EVENT}:
        raise PolicyProposalError("invalid_policy_version_event")
    record = {
        "event": event,
        "policy_component": _ensure_component(policy_component),
        "created_at": _ensure_iso_utc_z(created_at, "created_at"),
        "from_version_id": _ensure_non_empty_string(from_version_id, "from_version_id"),
        "to_version_id": _ensure_non_empty_string(to_version_id, "to_version_id"),
        "restored_value": _coerce_numeric(restored_value, "restored_value"),
        "operator_note": None if operator_note is None else _ensure_non_empty_string(operator_note, "operator_note"),
    }
    path = _version_event_log_path(observability_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def get_policy_version(observability_root: str | Path, policy_version_id: str) -> dict[str, Any] | None:
    target = _ensure_non_empty_string(policy_version_id, "policy_version_id")
    for item in reversed(list_policy_versions(observability_root, limit=200)):
        if item["policy_version_id"] == target:
            return item
    return None


def list_policy_versions(observability_root: str | Path, *, limit: int = 50) -> list[dict[str, Any]]:
    if not isinstance(limit, int) or limit < 1:
        raise PolicyProposalError("invalid_limit")
    bounded_limit = min(limit, 200)
    path = _version_log_path(observability_root)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise PolicyProposalError("unreadable_policy_versions") from exc
    items: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PolicyProposalError("unreadable_policy_versions") from exc
        if not isinstance(payload, dict):
            raise PolicyProposalError("invalid_policy_versions")
        items.append(_validate_version(payload))
    if len(items) <= bounded_limit:
        return items
    return items[-bounded_limit:]


def read_live_policy(runtime_root: str | Path) -> dict[str, Any]:
    path = _live_policy_path(runtime_root)
    if not path.exists():
        return {
            "policy_component": "auto_retry_threshold",
            "current_value": SUPPORTED_COMPONENTS["auto_retry_threshold"],
            "policy_version_id": None,
            "deployed_at": None,
            "proposal_id": None,
            "rollback_of_version_id": None,
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PolicyProposalError("unreadable_live_policy") from exc
    if not isinstance(payload, dict):
        raise PolicyProposalError("invalid_live_policy")
    return {
        "policy_component": _ensure_component(payload.get("policy_component")),
        "current_value": _coerce_numeric(payload.get("current_value"), "current_value"),
        "policy_version_id": payload.get("policy_version_id"),
        "deployed_at": payload.get("deployed_at"),
        "proposal_id": payload.get("proposal_id"),
        "rollback_of_version_id": payload.get("rollback_of_version_id"),
    }


def deploy_policy_version(
    runtime_root: str | Path,
    observability_root: str | Path,
    *,
    proposal_id: str,
    deployed_at: str,
    policy_component: str,
    new_value: float | str,
) -> dict[str, Any]:
    live = read_live_policy(runtime_root)
    component = _ensure_component(policy_component)
    previous_value = live["current_value"] if live["policy_component"] == component else SUPPORTED_COMPONENTS[component]
    record = _validate_version(
        {
            "deployed_at": deployed_at,
            "proposal_id": proposal_id,
            "policy_component": component,
            "previous_value": previous_value,
            "new_value": new_value,
            "status": ACTIVE_STATUS,
            "rollback_of_version_id": None,
        }
    )
    path = _version_log_path(observability_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    _write_json_atomic(
        _live_policy_path(runtime_root),
        {
            "policy_component": component,
            "current_value": record["new_value"],
            "policy_version_id": record["policy_version_id"],
            "deployed_at": record["deployed_at"],
            "proposal_id": proposal_id,
            "rollback_of_version_id": None,
        },
    )
    return record


def rollback_policy_version(
    runtime_root: str | Path,
    observability_root: str | Path,
    *,
    target_version_id: str,
    rolled_back_at: str,
    operator_note: str | None = None,
) -> dict[str, Any]:
    target = get_policy_version(observability_root, target_version_id)
    if target is None:
        raise PolicyProposalError("rollback_target_version_not_found")
    component = _ensure_component(target.get("policy_component"))
    live = read_live_policy(runtime_root)
    current_version_id = live.get("policy_version_id")
    if not isinstance(current_version_id, str) or not current_version_id.strip():
        raise PolicyProposalError("live_policy_version_missing")
    current_version = get_policy_version(observability_root, current_version_id)
    if current_version is None:
        raise PolicyProposalError("live_policy_version_missing")
    if current_version["policy_version_id"] == target["policy_version_id"]:
        raise PolicyProposalError("rollback_target_is_current_version")
    _append_version_event(
        observability_root,
        event=ROLLBACK_REQUESTED_EVENT,
        policy_component=component,
        created_at=rolled_back_at,
        from_version_id=current_version["policy_version_id"],
        to_version_id=target["policy_version_id"],
        restored_value=target["new_value"],
        operator_note=operator_note,
    )
    record = _validate_version(
        {
            "deployed_at": rolled_back_at,
            "proposal_id": None,
            "policy_component": component,
            "previous_value": live["current_value"],
            "new_value": target["new_value"],
            "status": ACTIVE_STATUS,
            "rollback_of_version_id": target["policy_version_id"],
        }
    )
    path = _version_log_path(observability_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    _write_json_atomic(
        _live_policy_path(runtime_root),
        {
            "policy_component": component,
            "current_value": record["new_value"],
            "policy_version_id": record["policy_version_id"],
            "deployed_at": record["deployed_at"],
            "proposal_id": None,
            "rollback_of_version_id": target["policy_version_id"],
        },
    )
    _append_version_event(
        observability_root,
        event=ROLLED_BACK_EVENT,
        policy_component=component,
        created_at=rolled_back_at,
        from_version_id=current_version["policy_version_id"],
        to_version_id=target["policy_version_id"],
        restored_value=target["new_value"],
        operator_note=operator_note,
    )
    return {
        "policy_component": component,
        "rolled_back_from_version_id": current_version["policy_version_id"],
        "rollback_target_version_id": target["policy_version_id"],
        "new_active_version_id": record["policy_version_id"],
        "current_value": record["new_value"],
    }
