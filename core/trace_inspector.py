"""
trace_inspector.py — Read-only trace inspection utilities.

Safety:
  - read-only: no trace mutation
  - returns structured JSON only

Output contract per trace summary:
  {
    "trace_id": str,
    "timestamp": str | None,
    "trace_version": str | None,
    "execution_mode": str | None,
    "intent": str | None,
    "result_status": str | None,
    "has_snapshot": bool,
  }

list_traces() contract:
  {
    "trace_count": int,
    "traces": [trace summary, ...],
    "feed_path": str,
  }

get_trace() contract:
  {
    "found": bool,
    "trace_id": str,
    "trace": trace summary | None,
  }
"""

import json
from pathlib import Path

from core.config import RUNTIME_LOGS_DIR
from core.snapshot_store import load_snapshot

TRACE_FILE = RUNTIME_LOGS_DIR / "activity_feed.jsonl"


def _has_snapshot(trace_id: str) -> bool:
    if not trace_id:
        return False
    try:
        return load_snapshot(trace_id) is not None
    except Exception:
        return False


def _summarise(record: dict) -> dict:
    task = record.get("normalized_task") or {}
    result = record.get("result") or {}
    trace_id = record.get("trace_id")

    return {
        "trace_id": trace_id,
        "timestamp": record.get("timestamp"),
        "trace_version": record.get("trace_version"),
        "execution_mode": record.get("execution_mode"),
        "intent": task.get("intent"),
        "result_status": result.get("status"),
        "has_snapshot": _has_snapshot(trace_id),
    }


def list_traces(limit: int = 20) -> dict:
    """
    Return the most recent traces from the activity feed.

    Args:
        limit: Maximum number of traces to return (default 20).

    Returns:
        {
          "trace_count": int,
          "traces": [trace summary, ...],   # most recent first
          "feed_path": str,
        }
    """
    if not TRACE_FILE.exists():
        return {"trace_count": 0, "traces": [], "feed_path": str(TRACE_FILE)}

    records = []
    with open(TRACE_FILE, "r") as f:
        for line in f:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    recent = list(reversed(records[-limit:] if len(records) > limit else records))
    summaries = [_summarise(r) for r in recent]

    return {
        "trace_count": len(summaries),
        "traces": summaries,
        "feed_path": str(TRACE_FILE),
    }


def get_trace(trace_id: str) -> dict:
    """
    Fetch a specific trace by trace_id — returns the full original record.

    Args:
        trace_id: The trace_id to look up.

    Returns:
        {
          "found": bool,
          "trace_id": str,
          "trace": <full raw trace record> | None,
        }

    Note: returns the complete record (all fields). For a reduced summary,
    use list_traces() which returns _summarise() objects.
    """
    if not TRACE_FILE.exists():
        return {"found": False, "trace_id": trace_id, "trace": None}

    with open(TRACE_FILE, "r") as f:
        for line in f:
            try:
                record = json.loads(line)
                if record.get("trace_id") == trace_id:
                    return {
                        "found": True,
                        "trace_id": trace_id,
                        "trace": record,
                    }
            except json.JSONDecodeError:
                continue

    return {"found": False, "trace_id": trace_id, "trace": None}
