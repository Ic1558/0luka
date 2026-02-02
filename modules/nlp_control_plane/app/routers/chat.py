"""
Chat Control Plane Router
=========================
Endpoints: /preview, /confirm, /watch, /stats

Slim router - business logic in core/.

SECURITY INVARIANTS:
- NO subprocess calls
- NO tool execution
- NO direct skill invocation
- ONLY: parse, cache, drop file, read telemetry
"""

from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timezone
import uuid

from ...core.contracts import (
    PreviewRequest, PreviewResponse,
    ConfirmRequest, ConfirmResponse,
    WatchResponse
)
from ...core.session_store import get_store
from ...core.normalizer import normalize_input, build_task_spec
from ...core.task_writer import write_task_file, TaskWriteError, TaskCollisionError
from ...core.watcher import watch_task_state
from ...core.telemetry import log_telemetry

router = APIRouter()

# ============================================================
# Endpoints
# ============================================================

@router.post("/preview", response_model=PreviewResponse)
async def preview_command(req: PreviewRequest):
    """
    Preview a command without executing.
    Returns structured TaskSpec for user confirmation.
    """
    store = get_store()

    # Normalize input
    normalized = normalize_input(req.raw_input)

    # Generate preview ID
    preview_id = str(uuid.uuid4())

    # Build task spec
    task_spec = build_task_spec(normalized, preview_id)

    # Store in session
    preview = store.store_preview(
        session_id=req.session_id,
        channel=req.channel,
        raw_input=req.raw_input,
        normalized_task=task_spec
    )

    # Log telemetry
    log_telemetry("preview", {
        "session_id": req.session_id,
        "channel": req.channel,
        "preview_id": preview.preview_id,
        "raw_input": req.raw_input,
        "intent": normalized["intent"],
        "risk": normalized["risk"]
    })

    return PreviewResponse(
        preview_id=preview.preview_id,
        normalized_task=task_spec,
        risk=normalized["risk"],
        lane="approval" if normalized["risk"] == "high" else "fast",
        requires_confirm=True,
        ttl_seconds=300
    )

@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_command(req: ConfirmRequest):
    """
    Confirm a previewed command and drop task file.
    """
    store = get_store()

    # Get preview
    preview = store.get_preview(req.preview_id, req.session_id)
    if not preview:
        raise HTTPException(400, detail="PREVIEW_EXPIRED: Preview not found or expired")

    task_spec = preview.normalized_task

    # Write task file
    try:
        task_id, target_path = write_task_file(task_spec)
    except TaskCollisionError:
        raise HTTPException(409, detail="TASK_COLLISION: Task ID already exists")
    except TaskWriteError as e:
        raise HTTPException(500, detail=str(e))

    # Mark as confirmed
    store.mark_confirmed(req.preview_id, req.session_id)

    # Log telemetry
    log_telemetry("confirm", {
        "session_id": req.session_id,
        "preview_id": req.preview_id,
        "task_id": task_id,
        "path": str(target_path),
        "lane": task_spec.get("lane", "task")
    })

    lane_msg = "pending approval" if "pending_approval" in str(target_path) else "inbox"

    return ConfirmResponse(
        status="ok",
        task_id=task_id,
        path_written=str(target_path),
        ack=f"Task {task_id} submitted to {lane_msg}"
    )

@router.get("/watch/{task_id}", response_model=WatchResponse)
async def watch_task(
    task_id: str,
    session_id: str = Query(..., min_length=36, max_length=36)
):
    """
    Watch task state by reading telemetry.
    READ-ONLY - no execution.
    """
    try:
        state, last_event, result_summary = watch_task_state(task_id)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    # Log telemetry
    log_telemetry("watch", {
        "session_id": session_id,
        "task_id": task_id,
        "state": state
    })

    return WatchResponse(
        task_id=task_id,
        state=state,
        last_event=last_event,
        result_summary=result_summary,
        updated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )

@router.get("/stats")
async def get_stats():
    """Return session store statistics."""
    store = get_store()
    return store.stats()
