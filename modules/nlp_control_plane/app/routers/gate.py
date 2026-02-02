"""
Gate Router - Approval/Rejection Endpoints
==========================================
COPY EXACT from tools/web_bridge/routers/gate.py
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import yaml
import shutil

from ...core.contracts import GateItem, GateVerdict
from ...core.guards import assert_write_scope, INTERFACE_ROOT

router = APIRouter()

PENDING_ROOT = INTERFACE_ROOT / "pending_approval"
INBOX_ROOT = INTERFACE_ROOT / "inbox"
REJECTED_ROOT = INTERFACE_ROOT / "rejected"

@router.get("/pending", response_model=list[GateItem])
async def list_pending():
    items = []
    # Scan pending_approval/ for yaml files
    if not PENDING_ROOT.exists():
        return []

    for f in PENDING_ROOT.glob("*.yaml"):
        try:
            data = yaml.safe_load(f.read_text()) or {}
            # Check for Vera's verdict (sidecar file or field?)
            # Spec says "Vera's Verdict (PASS/FAIL/MISSING)"
            # Assuming vera writes {filename}.verdict.json or updates yaml
            # For v1.0, we check for a 'vera_verdict' field in YAML or default to MISSING

            verdict = data.get("vera_verdict", GateVerdict.MISSING)

            items.append(GateItem(
                task_id=data.get("task_id", "unknown"),
                intent=data.get("intent", "unknown"),
                author=data.get("author", "unknown"),
                ts_utc=data.get("created_at_utc", ""),
                path=f.name,
                vera_verdict=verdict,
                risk_level=data.get("risk_level", "unknown")
            ))
        except Exception:
            continue

    return items

@router.post("/{task_id}/approve")
async def approve_task(task_id: str):
    # Security: Validate task_id format to prevent traversal
    if ".." in task_id or "/" in task_id:
        raise HTTPException(400, "Invalid Task ID")

    src = PENDING_ROOT / f"{task_id}.yaml"
    if not src.exists():
        # Fallback: maybe it's named slightly differently or we need map
        raise HTTPException(404, "Task not found in pending")

    # Move to Inbox (High Priority ideally, but inbox is fine)
    dst = INBOX_ROOT / f"{task_id}.yaml"

    # Assert Scopes
    assert_write_scope(src)
    assert_write_scope(dst)

    try:
        shutil.move(str(src), str(dst))
        # Optional: Write approval record?
    except Exception as e:
        raise HTTPException(500, f"Move failed: {e}")

    return {"status": "approved", "path": str(dst)}

@router.post("/{task_id}/reject")
async def reject_task(task_id: str):
    if ".." in task_id or "/" in task_id:
        raise HTTPException(400, "Invalid Task ID")

    src = PENDING_ROOT / f"{task_id}.yaml"
    if not src.exists():
        raise HTTPException(404, "Task not found in pending")

    dst = REJECTED_ROOT / f"{task_id}.yaml"

    assert_write_scope(src)
    assert_write_scope(dst)

    try:
        shutil.move(str(src), str(dst))
    except Exception as e:
        raise HTTPException(500, f"Move failed: {e}")

    return {"status": "rejected", "path": str(dst)}
