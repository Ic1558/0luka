#!/usr/bin/env python3
"""
Timeline Event Emitter - structured event log for task lifecycle.

Each task gets a timeline.jsonl file under observability/artifacts/tasks/<trace_id>/.
Events follow the replay_task.py state machine:
  START → PENDING → DISPATCHED → RUNNING → RESULT_RECEIVED → DONE
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

ROOT = Path(os.environ.get("ROOT") or Path(__file__).resolve().parents[1])
ARTIFACTS_DIR = ROOT / "observability" / "artifacts" / "tasks"


def emit_event(
    trace_id: str,
    task_id: str,
    event: str,
    *,
    phase: str = "",
    agent_id: str = "",
    detail: str = "",
    extra: Optional[dict] = None,
) -> Path:
    """Append a structured event to the task's timeline.jsonl."""
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry = {
        "ts": ts,
        "trace_id": trace_id,
        "task_id": task_id,
        "event": event,
        "phase": phase,
        "agent_id": agent_id,
    }
    if detail:
        entry["detail"] = detail
    if extra and isinstance(extra, dict):
        entry.update(extra)

    task_dir = ARTIFACTS_DIR / trace_id
    task_dir.mkdir(parents=True, exist_ok=True)
    timeline_path = task_dir / "timeline.jsonl"
    with timeline_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return timeline_path


def read_timeline(trace_id: str) -> list:
    """Read all events for a given trace_id."""
    timeline_path = ARTIFACTS_DIR / trace_id / "timeline.jsonl"
    if not timeline_path.exists():
        return []
    events = []
    for line in timeline_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events
