#!/usr/bin/env python3
"""
knowledge_writer.py — Schema-validated writer for g/knowledge/ derivative annotation files.

g/knowledge is derivative annotation only.
Every record MUST carry:
  - trace_id  pointing to an existing activity_feed or dispatcher event
  - evidence_ref  pointing to an authoritative artifact, file, or feed entry

Records missing either field are rejected. g/knowledge must never become a source of truth.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

KNOWLEDGE_DIR = _REPO_ROOT / "g" / "knowledge"
MLS_LESSONS_PATH = KNOWLEDGE_DIR / "mls_lessons.jsonl"
SOLUTION_LEDGER_PATH = KNOWLEDGE_DIR / "solution_ledger.jsonl"

_REQUIRED_FIELDS = ("trace_id", "evidence_ref")


def _validate(record: Dict[str, Any]) -> None:
    """Raise ValueError if record is missing required fields."""
    missing = [f for f in _REQUIRED_FIELDS if not str(record.get(f) or "").strip()]
    if missing:
        raise ValueError(
            f"knowledge_writer: record rejected — missing required fields: {missing}. "
            "Every g/knowledge record must carry trace_id and evidence_ref."
        )


def _append_atomic(path: Path, record: Dict[str, Any]) -> None:
    """Append one JSON line atomically (no partial writes)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    # Read existing + append, then atomically replace.
    existing = path.read_bytes() if path.exists() else b""
    tmp.write_bytes(existing + line.encode("utf-8"))
    os.replace(tmp, path)


def write_lesson(record: Dict[str, Any]) -> None:
    """
    Append a lesson record to mls_lessons.jsonl.
    Required fields: trace_id, evidence_ref.
    Expected schema: { ts, trace_id, lesson_type, description, evidence_ref }
    """
    _validate(record)
    if "ts" not in record:
        record = {**record, "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    _append_atomic(MLS_LESSONS_PATH, record)


def write_solution(record: Dict[str, Any]) -> None:
    """
    Append a solution record to solution_ledger.jsonl.
    Required fields: trace_id, evidence_ref.
    Expected schema: { ts, problem_pattern, solution_applied, outcome, trace_id, evidence_ref }
    """
    _validate(record)
    if "ts" not in record:
        record = {**record, "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    _append_atomic(SOLUTION_LEDGER_PATH, record)
