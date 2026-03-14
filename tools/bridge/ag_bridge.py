from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

from core.activity_feed_guard import guarded_append_activity_feed
from core.policy.get_active_policy import get_active_policy
from core.submit import submit_task

ALLOWED_AGENTS = frozenset({"cole", "lisa"})
ALLOWED_TASKS = frozenset({"cole.search_docs", "lisa.exec_shell"})

TASK_LANE_MAP: dict[str, str] = {
    "cole.search_docs": "cole",
    "lisa.exec_shell": "lisa",
}


@dataclass
class AgBridgeResponse:
    request_id: str
    status: str  # accepted | rejected | blocked
    task_id: str | None
    error: str | None
    policy_blocked: bool = False


def dispatch(request: dict[str, Any], *, policy_path: Optional[Path] = None) -> AgBridgeResponse:
    """Validate, gate, and submit an Antigravity bridge request."""
    request_id = str((request or {}).get("id") or uuid.uuid4())
    try:
        ok, reason = _validate_request(request or {})
        if not ok:
            return _reject(request_id, reason)

        source = str(request.get("source", ""))
        if source != "antigravity":
            return _reject(request_id, "invalid:source")

        agent = str(request.get("agent") or "")
        task = str(request.get("task") or "")
        if agent not in ALLOWED_AGENTS:
            return _reject(request_id, f"invalid:agent:{agent}")
        if task not in ALLOWED_TASKS:
            return _reject(request_id, f"invalid:task:{task}")

        try:
            policy = get_active_policy(policy_path)
        except RuntimeError as exc:
            return _reject(request_id, f"policy_read_error:{exc}")

        if policy.freeze_state:
            return _blocked(request_id, agent=agent, task=task)

        lane = TASK_LANE_MAP[task]
        created_at = str(request.get("created_at_utc") or _utc_now())
        args = request.get("args") or {}
        if not isinstance(args, dict):
            return _reject(request_id, "invalid:args")

        # Submit via existing core.submit pipeline only.
        task_dict: dict[str, Any] = {
            "task_id": request_id,
            "author": "antigravity",
            "intent": task,
            "lane": lane,
            "executor": lane,
            "created_at_utc": created_at,
            "operations": [
                {
                    "id": f"{request_id}:op1",
                    "tool": task,
                    "params": args,
                }
            ],
        }

        try:
            receipt = submit_task(task_dict, task_id=request_id)
            submitted_task_id = str(receipt["task_id"])
        except Exception as exc:
            return _reject(request_id, f"submit_error:{exc}", agent=agent, task=task)

        _audit(request_id, agent, task, "accepted", task_id=submitted_task_id)
        return AgBridgeResponse(
            request_id=request_id,
            status="accepted",
            task_id=submitted_task_id,
            error=None,
            policy_blocked=False,
        )
    except Exception as exc:
        return _reject(request_id, f"dispatch_error:{exc}")


def _validate_request(request: dict[str, Any]) -> tuple[bool, str]:
    schema = _load_request_schema()
    required = schema.get("required") or []
    for key in required:
        if key not in request:
            return False, f"invalid:missing:{key}"

    if request.get("source") != "antigravity":
        return False, "invalid:source"
    if str(request.get("agent") or "") not in ALLOWED_AGENTS:
        return False, f"invalid:agent:{request.get('agent')}"
    if str(request.get("task") or "") not in ALLOWED_TASKS:
        return False, f"invalid:task:{request.get('task')}"
    if not isinstance(request.get("args"), dict):
        return False, "invalid:args"
    return True, ""


def _load_request_schema() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "interface" / "schemas" / "ag_bridge_request_v1.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _reject(
    request_id: str,
    reason: str,
    *,
    agent: str = "-",
    task: str = "-",
) -> AgBridgeResponse:
    _audit(request_id, agent, task, "rejected", reason=reason)
    return AgBridgeResponse(
        request_id=request_id,
        status="rejected",
        task_id=None,
        error=reason,
        policy_blocked=False,
    )


def _blocked(request_id: str, *, agent: str, task: str) -> AgBridgeResponse:
    _audit(request_id, agent, task, "blocked", reason="policy_freeze")
    return AgBridgeResponse(
        request_id=request_id,
        status="blocked",
        task_id=None,
        error="blocked_by_policy_freeze",
        policy_blocked=True,
    )


def _audit(
    request_id: str,
    agent: str,
    task: str,
    status: str,
    *,
    task_id: str = "-",
    reason: str = "",
) -> None:
    payload = {
        "ts_utc": _utc_now(),
        "category": "bridge_request",
        "source": "antigravity",
        "agent": agent,
        "task": task,
        "request_id": request_id,
        "task_id": task_id,
        "status": status,
        "reason": reason,
    }
    try:
        feed_path = _resolve_activity_feed_path()
        guarded_append_activity_feed(feed_path, payload)
    except Exception:
        pass


def _resolve_activity_feed_path() -> Path:
    return Path(__file__).resolve().parents[2] / "observability" / "logs" / "activity_feed.jsonl"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

