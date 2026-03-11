from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.ops.control_plane_persistence import DecisionPersistenceError, read_decision_history


SUCCESS_STATUSES = {"committed", "ok", "success", "completed", "dry_run_ok"}
FAILURE_AUDIT_DECISIONS = {"rejected", "error"}
EXECUTION_EVENTS = {
    "EXECUTION_HANDOFF_ACCEPTED",
    "EXECUTION_RETRY_REQUESTED",
    "EXECUTION_ESCALATION_REQUESTED",
}


def _safe_relative(path: Path, root: Path) -> str | None:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return None


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("invalid_json_object")
    return payload


def _latest_attempt_context(decision_id: str, observability_root: Path) -> dict[str, Any] | None:
    rows = read_decision_history(observability_root, limit=200)
    latest_event: dict[str, Any] | None = None
    retry_count = 0
    escalation_count = 0

    for row in rows:
        if row.get("decision_id") != decision_id:
            continue
        event = row.get("event")
        if event not in EXECUTION_EVENTS:
            continue
        latest_event = row
        if event == "EXECUTION_RETRY_REQUESTED":
            retry_count += 1
        elif event == "EXECUTION_ESCALATION_REQUESTED":
            escalation_count += 1

    if latest_event is None:
        return None

    event = str(latest_event.get("event") or "")
    if event == "EXECUTION_HANDOFF_ACCEPTED":
        task_id = f"decision_exec_{decision_id}"
    elif event == "EXECUTION_RETRY_REQUESTED":
        task_id = f"decision_exec_{decision_id}_retry_{retry_count}"
    else:
        task_id = f"decision_exec_{decision_id}_escalate_{escalation_count}"

    return {
        "latest_event": latest_event,
        "task_id": task_id,
        "retry_count": retry_count,
        "escalation_count": escalation_count,
    }


def reconcile_execution_outcome(
    decision: dict[str, Any] | None,
    *,
    repo_root: Path,
    observability_root: Path,
) -> dict[str, Any] | None:
    if not isinstance(decision, dict):
        return None

    decision_id = decision.get("decision_id")
    if not isinstance(decision_id, str) or not decision_id.strip():
        return None

    try:
        attempt = _latest_attempt_context(decision_id, observability_root)
    except DecisionPersistenceError:
        return {
            "bridge_status": "HANDOFF_ACCEPTED",
            "outcome_status": "EXECUTION_UNKNOWN",
            "outcome_ref": None,
            "retry_count": 0,
            "escalation_count": 0,
        }

    if attempt is None:
        return None

    task_id = attempt["task_id"]
    outbox_path = repo_root / "interface" / "outbox" / "tasks" / f"{task_id}.result.json"
    audit_path = repo_root / "observability" / "artifacts" / "router_audit" / f"{task_id}.json"

    if outbox_path.exists():
        try:
            payload = _read_json(outbox_path)
        except Exception:
            return {
                "bridge_status": "HANDOFF_ACCEPTED",
                "outcome_status": "EXECUTION_UNKNOWN",
                "outcome_ref": _safe_relative(outbox_path, repo_root),
                "retry_count": attempt["retry_count"],
                "escalation_count": attempt["escalation_count"],
            }
        status = str(payload.get("status") or "").strip().lower()
        if status in SUCCESS_STATUSES:
            return {
                "bridge_status": "HANDOFF_ACCEPTED",
                "outcome_status": "EXECUTION_SUCCEEDED",
                "outcome_ref": _safe_relative(outbox_path, repo_root),
                "retry_count": attempt["retry_count"],
                "escalation_count": attempt["escalation_count"],
            }
        return {
            "bridge_status": "HANDOFF_ACCEPTED",
            "outcome_status": "EXECUTION_UNKNOWN",
            "outcome_ref": _safe_relative(outbox_path, repo_root),
            "retry_count": attempt["retry_count"],
            "escalation_count": attempt["escalation_count"],
        }

    if audit_path.exists():
        try:
            payload = _read_json(audit_path)
        except Exception:
            return {
                "bridge_status": "HANDOFF_ACCEPTED",
                "outcome_status": "EXECUTION_UNKNOWN",
                "outcome_ref": _safe_relative(audit_path, repo_root),
                "retry_count": attempt["retry_count"],
                "escalation_count": attempt["escalation_count"],
            }
        decision_value = str(payload.get("decision") or "").strip().lower()
        if decision_value in FAILURE_AUDIT_DECISIONS:
            return {
                "bridge_status": "HANDOFF_ACCEPTED",
                "outcome_status": "EXECUTION_FAILED",
                "outcome_ref": _safe_relative(audit_path, repo_root),
                "retry_count": attempt["retry_count"],
                "escalation_count": attempt["escalation_count"],
            }
        return {
            "bridge_status": "HANDOFF_ACCEPTED",
            "outcome_status": "EXECUTION_UNKNOWN",
            "outcome_ref": _safe_relative(audit_path, repo_root),
            "retry_count": attempt["retry_count"],
            "escalation_count": attempt["escalation_count"],
        }

    return {
        "bridge_status": "HANDOFF_ACCEPTED",
        "outcome_status": "HANDOFF_ONLY",
        "outcome_ref": None,
        "retry_count": attempt["retry_count"],
        "escalation_count": attempt["escalation_count"],
    }
