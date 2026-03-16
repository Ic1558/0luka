"""AG-32: Drift Governance Store — append-only governance history + latest status map.

State files (under $LUKA_RUNTIME_ROOT/state/):
  drift_finding_status.json       — latest status per finding_id (dict)
  drift_governance_log.jsonl      — append-only operator action history
  drift_baseline_proposals.jsonl  — append-only baseline promotion proposals

Invariants:
  - latest status = atomic write (temp + os.replace)
  - history = append-only, never deleted or rewritten
  - fail-closed if LUKA_RUNTIME_ROOT not set
  - read-only functions never raise on missing files (return empty)
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


_STATUS_FILE = "drift_finding_status.json"
_LOG_FILE = "drift_governance_log.jsonl"
_PROPOSALS_FILE = "drift_baseline_proposals.jsonl"


def _state_dir() -> Path:
    rt = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Append-only log writers
# ---------------------------------------------------------------------------

def append_governance_log(record: dict[str, Any]) -> None:
    """Append a single operator action record to drift_governance_log.jsonl."""
    path = _state_dir() / _LOG_FILE
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def append_baseline_proposal(record: dict[str, Any]) -> None:
    """Append a baseline promotion proposal record."""
    path = _state_dir() / _PROPOSALS_FILE
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


# ---------------------------------------------------------------------------
# Latest status map (atomic read/write)
# ---------------------------------------------------------------------------

def load_finding_status() -> dict[str, dict[str, Any]]:
    """Load the full finding_id → status map. Returns {} if not yet created."""
    try:
        path = _state_dir() / _STATUS_FILE
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_finding_status(status_map: dict[str, dict[str, Any]]) -> None:
    """Atomically overwrite the full status map."""
    path = _state_dir() / _STATUS_FILE
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(status_map, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def set_finding_status(
    finding_id: str,
    new_status: str,
    operator_id: str,
    note: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update the status of a finding and append to governance log.

    Returns the updated status record.
    """
    ts = _now()
    record: dict[str, Any] = {
        "finding_id": finding_id,
        "status": new_status,
        "updated_at": ts,
        "operator_id": operator_id,
        "note": note or "",
        **(extra or {}),
    }

    # Update latest status map (atomic)
    status_map = load_finding_status()
    status_map[finding_id] = record
    save_finding_status(status_map)

    # Append to governance log
    log_record = {
        "ts": ts,
        "finding_id": finding_id,
        "action": new_status,
        "operator_id": operator_id,
        "note": note or "",
    }
    if extra:
        log_record.update(extra)
    append_governance_log(log_record)

    return record


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def get_finding_status(finding_id: str) -> dict[str, Any] | None:
    """Return the latest status record for a finding, or None if not found."""
    return load_finding_status().get(finding_id)


def list_finding_status(status_filter: str | None = None) -> list[dict[str, Any]]:
    """List all finding status records, optionally filtered by status value."""
    status_map = load_finding_status()
    records = list(status_map.values())
    if status_filter:
        records = [r for r in records if r.get("status") == status_filter]
    return records


def list_governance_log(limit: int = 200) -> list[dict[str, Any]]:
    """Return the most recent N governance log entries (append-only)."""
    try:
        path = _state_dir() / _LOG_FILE
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        result = []
        for line in lines[-limit:]:
            try:
                result.append(json.loads(line))
            except Exception:
                pass
        return result
    except Exception:
        return []


def list_baseline_proposals(limit: int = 100) -> list[dict[str, Any]]:
    """Return recent baseline promotion proposals."""
    try:
        path = _state_dir() / _PROPOSALS_FILE
        if not path.exists():
            return []
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        result = []
        for line in lines[-limit:]:
            try:
                result.append(json.loads(line))
            except Exception:
                pass
        return result
    except Exception:
        return []
