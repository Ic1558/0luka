"""AG-30: Outcome governance store — append-only log + latest pointer per policy.

State files (under LUKA_RUNTIME_ROOT/state/):
  policy_outcome_governance.jsonl   append-only history of governance records
  policy_outcome_latest.json        dict of policy_id → latest governance record

Record shape:
  {
    "governance_id":          "<uuid-hex>",
    "policy_id":              "...",
    "effectiveness_verdict":  "ROLLBACK_RECOMMENDED",
    "recommended_action":     "ROLLBACK_CANDIDATE",
    "rationale":              "...",
    "status":                 "PENDING_OPERATOR",
    "created_at":             "...",
    "actioned_at":            null,
    "actioned_by":            null,
    "action_taken":           null,
    "before_failures":        3,
    "after_failures":         5,
    ...
  }

Status lifecycle:
  PENDING_OPERATOR → ACTIONED   (operator executed an action)
  PENDING_OPERATOR → DISMISSED  (operator explicitly dismissed)
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


_LOG_NAME = "policy_outcome_governance.jsonl"
_LATEST_NAME = "policy_outcome_latest.json"


def _state_dir() -> Path:
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    d = Path(runtime_root) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def create_governance_record(recommendation: dict[str, Any]) -> dict[str, Any]:
    """Build a new governance record from an outcome_router recommendation."""
    return {
        "governance_id": uuid.uuid4().hex[:12],
        "policy_id": str(recommendation.get("policy_id") or ""),
        "effectiveness_verdict": str(recommendation.get("effectiveness_verdict") or ""),
        "recommended_action": str(recommendation.get("recommended_action") or ""),
        "rationale": str(recommendation.get("rationale") or ""),
        "status": "PENDING_OPERATOR",
        "created_at": _now(),
        "actioned_at": None,
        "actioned_by": None,
        "action_taken": None,
        # evidence pass-through
        "before_failures": recommendation.get("before_failures"),
        "after_failures": recommendation.get("after_failures"),
        "baseline_failure_rate": recommendation.get("baseline_failure_rate"),
        "post_failure_rate": recommendation.get("post_failure_rate"),
        "delta": recommendation.get("delta"),
        "before_count": recommendation.get("before_count"),
        "after_count": recommendation.get("after_count"),
    }


def append_governance_record(record: dict[str, Any]) -> dict[str, Any]:
    """Append one governance record to the log. Returns the record."""
    log_path = _state_dir() / _LOG_NAME
    existing = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    tmp = log_path.with_suffix(".tmp")
    tmp.write_text(existing + json.dumps(record) + "\n", encoding="utf-8")
    os.replace(tmp, log_path)
    return record


def write_latest(record: dict[str, Any]) -> None:
    """Atomically upsert latest governance record for a policy_id."""
    latest_path = _state_dir() / _LATEST_NAME
    try:
        current: dict[str, Any] = json.loads(latest_path.read_text(encoding="utf-8")) if latest_path.exists() else {}
    except (json.JSONDecodeError, OSError):
        current = {}
    policy_id = str(record.get("policy_id") or "")
    if policy_id:
        current[policy_id] = record
    tmp = latest_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(current, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, latest_path)


def update_governance_record(governance_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    """Update a governance record in the log (appends updated version) and latest.

    Returns the updated record, or None if not found.
    """
    log_path = _state_dir() / _LOG_NAME
    if not log_path.exists():
        return None

    records = list_governance_log(limit=10000)
    target: dict[str, Any] | None = None
    for r in reversed(records):
        if r.get("governance_id") == governance_id:
            target = dict(r)
            break
    if target is None:
        return None

    target.update(updates)
    # append the updated record (log is append-only; consumers use latest per governance_id)
    append_governance_record(target)
    write_latest(target)
    return target


def list_governance_log(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent governance records from the log (newest last)."""
    log_path = _state_dir() / _LOG_NAME
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return records[-limit:]


def get_latest_for_policy(policy_id: str) -> dict[str, Any] | None:
    """Return the latest governance record for a policy, or None."""
    latest_path = _state_dir() / _LATEST_NAME
    if not latest_path.exists():
        return None
    try:
        data = json.loads(latest_path.read_text(encoding="utf-8"))
        return data.get(policy_id)
    except (json.JSONDecodeError, OSError):
        return None


def list_all_latest() -> list[dict[str, Any]]:
    """Return all latest governance records across policies."""
    latest_path = _state_dir() / _LATEST_NAME
    if not latest_path.exists():
        return []
    try:
        return list(json.loads(latest_path.read_text(encoding="utf-8")).values())
    except (json.JSONDecodeError, OSError):
        return []
