"""
Task Writer for NLP Control Plane
=================================
Write task files to inbox/pending_approval.

COPY EXACT from tools/web_bridge/routers/chat.py confirm endpoint logic
"""

from pathlib import Path
from typing import Dict, Any, Tuple
import yaml

from .guards import assert_write_scope, assert_safe_filename, INTERFACE_ROOT


class TaskWriteError(Exception):
    """Raised when task write fails."""
    pass


class TaskCollisionError(Exception):
    """Raised when task ID already exists."""
    pass


def write_task_file(task_spec: Dict[str, Any]) -> Tuple[str, Path]:
    """
    Write task file to appropriate lane directory.

    Returns (task_id, path_written).
    Raises TaskWriteError or TaskCollisionError on failure.
    """
    task_id = task_spec["task_id"]

    # Generate filename
    filename = f"{task_id}.yaml"
    assert_safe_filename(filename)

    # Determine target path based on lane
    if task_spec.get("lane") == "approval" or task_spec["operations"][0]["risk_hint"] == "high":
        target_dir = INTERFACE_ROOT / "pending_approval"
    else:
        target_dir = INTERFACE_ROOT / "inbox"

    target_path = target_dir / filename

    # Assert write scope
    assert_write_scope(target_path)

    # Check collision
    if target_path.exists():
        raise TaskCollisionError(f"Task ID {task_id} already exists")

    # Ensure directory exists
    target_dir.mkdir(parents=True, exist_ok=True)

    # Write file atomically
    try:
        # Remove preview_id from final task (internal only)
        final_task = {k: v for k, v in task_spec.items() if k != "preview_id"}

        tmp_path = target_path.with_suffix(".tmp")
        with open(tmp_path, "w") as f:
            yaml.safe_dump(final_task, f, sort_keys=False)
        tmp_path.rename(target_path)
    except Exception as e:
        raise TaskWriteError(f"Write failed: {e}")

    return task_id, target_path
