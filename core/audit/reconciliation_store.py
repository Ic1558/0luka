"""AG-35: Reconciliation Store.

Append-only log + atomic latest summary for drift repair reconciliation records.

Runtime outputs:
  $LUKA_RUNTIME_ROOT/state/repair_reconciliation_log.jsonl  — append-only
  $LUKA_RUNTIME_ROOT/state/repair_reconciliation_latest.json — atomic overwrite

Invariants:
  - log is append-only, never truncated
  - latest summary is atomically overwritten
  - fail-closed if LUKA_RUNTIME_ROOT not set
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _state_dir(runtime_root: str | None = None) -> Path:
    rt = runtime_root or os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not rt:
        raise RuntimeError("LUKA_RUNTIME_ROOT is required (fail-closed).")
    d = Path(rt) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Append-only reconciliation log
# ---------------------------------------------------------------------------

def append_reconciliation_log(record: dict[str, Any], runtime_root: str | None = None) -> None:
    """Append a reconciliation record to repair_reconciliation_log.jsonl."""
    log_path = _state_dir(runtime_root) / "repair_reconciliation_log.jsonl"
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def list_reconciliation_records(runtime_root: str | None = None) -> list[dict[str, Any]]:
    """Return all reconciliation records from the log."""
    try:
        log_path = _state_dir(runtime_root) / "repair_reconciliation_log.jsonl"
        if not log_path.exists():
            return []
        results = []
        for line in log_path.read_text(encoding="utf-8").strip().splitlines():
            try:
                results.append(json.loads(line))
            except Exception:
                pass
        return results
    except Exception:
        return []


def get_reconciliation_record(reconciliation_id: str, runtime_root: str | None = None) -> dict[str, Any] | None:
    """Return the reconciliation record with the given reconciliation_id, or None."""
    for record in list_reconciliation_records(runtime_root):
        if record.get("reconciliation_id") == reconciliation_id:
            return record
    return None


# ---------------------------------------------------------------------------
# Atomic latest summary
# ---------------------------------------------------------------------------

def save_reconciliation_latest(summary: dict[str, Any], runtime_root: str | None = None) -> None:
    """Atomically overwrite repair_reconciliation_latest.json."""
    state_d = _state_dir(runtime_root)
    path = state_d / "repair_reconciliation_latest.json"
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass


def load_reconciliation_latest(runtime_root: str | None = None) -> dict[str, Any]:
    """Load the latest reconciliation summary, or return empty dict."""
    try:
        path = _state_dir(runtime_root) / "repair_reconciliation_latest.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Record factory
# ---------------------------------------------------------------------------

def new_reconciliation_id() -> str:
    return "recon-" + uuid.uuid4().hex[:8]
