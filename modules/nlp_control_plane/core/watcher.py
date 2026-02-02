"""
Task Watcher for NLP Control Plane
==================================
Read-only task state monitoring via telemetry.

COPY EXACT from tools/web_bridge/routers/chat.py watch endpoint logic
"""

from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import json

from .guards import INTERFACE_ROOT


# Telemetry sources for state inference
TELEMETRY_FILES = [
    Path("/Users/icmini/0luka/observability/telemetry/bridge_consumer.latest.json"),
    Path("/Users/icmini/0luka/observability/telemetry/executor_lisa.latest.json"),
]


def watch_task_state(task_id: str) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
    """
    Watch task state by reading telemetry.
    READ-ONLY - no execution.

    Returns (state, last_event, result_summary).
    State is one of: unknown, accepted, pending_approval, running, done, failed
    """
    # Validate task_id format
    if ".." in task_id or "/" in task_id:
        raise ValueError("Invalid task ID")

    # Search for task state in telemetry
    state = "unknown"
    last_event = None
    result_summary = None

    # Check multiple telemetry sources
    for telem_file in TELEMETRY_FILES:
        if telem_file.exists():
            try:
                data = json.loads(telem_file.read_text())
                if data.get("task_id") == task_id or task_id in str(data):
                    last_event = data
                    # Infer state from telemetry
                    if "done" in str(data).lower() or data.get("status") == "done":
                        state = "done"
                    elif "running" in str(data).lower() or data.get("status") == "running":
                        state = "running"
                    elif "error" in str(data).lower() or data.get("status") == "error":
                        state = "failed"
                    else:
                        state = "accepted"
                    break
            except Exception:
                continue

    # Check inbox/pending_approval for state
    inbox_path = INTERFACE_ROOT / "inbox" / f"{task_id}.yaml"
    pending_path = INTERFACE_ROOT / "pending_approval" / f"{task_id}.yaml"
    completed_path = INTERFACE_ROOT / "completed" / f"{task_id}.yaml"

    if completed_path.exists():
        state = "done"
    elif pending_path.exists():
        state = "pending_approval"
    elif inbox_path.exists():
        state = "accepted"

    return state, last_event, result_summary
