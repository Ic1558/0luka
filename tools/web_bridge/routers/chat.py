"""
Chat Control Plane Router
=========================
Endpoints: /preview, /confirm, /watch

SECURITY INVARIANTS:
- NO subprocess calls
- NO tool execution
- NO direct skill invocation
- ONLY: parse, cache, drop file, read telemetry
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime, timezone
from pathlib import Path
import uuid
import yaml
import json
import re

from ..session_store import get_store, Preview
from ..models import TaskSpec, TaskOperation, RiskLevel
from ..utils.rw_guard import assert_write_scope, assert_safe_filename, INTERFACE_ROOT

router = APIRouter()

# ============================================================
# Models
# ============================================================

class PreviewRequest(BaseModel):
    raw_input: str = Field(..., min_length=1, max_length=1000)
    channel: Literal["terminal", "telegram", "api"] = "terminal"
    session_id: str = Field(..., min_length=36, max_length=36)

class PreviewResponse(BaseModel):
    preview_id: str
    normalized_task: Dict[str, Any]
    risk: Literal["low", "high"]
    lane: Literal["fast", "approval"]
    requires_confirm: bool = True
    ttl_seconds: int = 300

class ConfirmRequest(BaseModel):
    preview_id: str
    session_id: str

class ConfirmResponse(BaseModel):
    status: Literal["ok", "error"]
    task_id: str
    path_written: str
    ack: str

class WatchResponse(BaseModel):
    task_id: str
    state: Literal["unknown", "accepted", "pending_approval", "running", "done", "failed"]
    last_event: Optional[Dict[str, Any]] = None
    result_summary: Optional[str] = None
    updated_at: str

# ============================================================
# NLP Normalizer (Rule-based v1)
# ============================================================

INTENT_PATTERNS = [
    # Pattern, intent, tool, risk
    (r"^(liam\s+)?(check|show|get)\s+status$", "status_check", "status_reader", "low"),
    (r"^(liam\s+)?session\s+(start|begin)", "session_start", "session_manager", "low"),
    (r"^(show|list)\s+(tasks?|pending|inbox)", "task_list", "inbox_reader", "low"),
    (r"^(liam\s+)?plan\s+", "planning", "planner", "low"),
    (r"^(lisa\s+)?(run|execute)\s+", "task_execution", "task_runner", "high"),
    (r"^(vera\s+)?(verify|audit|check)\s+", "verification", "verifier", "low"),
]

def normalize_input(raw_input: str) -> Dict[str, Any]:
    """
    Convert natural language to structured TaskSpec.

    NO EXECUTION - only parsing and structuring.
    """
    text = raw_input.strip().lower()

    for pattern, intent, tool, risk in INTENT_PATTERNS:
        if re.match(pattern, text):
            return {
                "intent": intent,
                "tool": tool,
                "risk": risk,
                "params": {"raw": raw_input},
                "matched_pattern": pattern
            }

    # Fallback: unknown
    return {
        "intent": "unknown",
        "tool": "unknown",
        "risk": "high",
        "params": {"raw": raw_input},
        "matched_pattern": None
    }

def build_task_spec(normalized: Dict[str, Any], preview_id: str) -> Dict[str, Any]:
    """Build a TaskSpec v2 compatible structure."""
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d_%H%M%S")
    rand = uuid.uuid4().hex[:6]
    task_id = f"task_{ts}_{rand}"

    return {
        "task_id": task_id,
        "author": "gmx",  # Server-enforced
        "intent": normalized["intent"],
        "operations": [{
            "id": "op_1",
            "tool": normalized["tool"],
            "params": normalized["params"],
            "risk_hint": normalized["risk"]
        }],
        "created_at_utc": now.isoformat().replace("+00:00", "Z"),
        "lane": "approval" if normalized["risk"] == "high" else "task",
        "reply_to": "interface/outbox/tasks",
        "preview_id": preview_id
    }

# ============================================================
# Telemetry Logger
# ============================================================

TELEMETRY_PATH = Path("/Users/icmini/0luka/observability/telemetry/gateway.jsonl")

def log_telemetry(event: str, data: Dict[str, Any]) -> None:
    """Append event to gateway telemetry log."""
    try:
        entry = {
            "ts_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "module": "chat_gateway",
            "event": event,
            **data
        }
        TELEMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TELEMETRY_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass  # Non-critical, don't fail request

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
        raise HTTPException(409, detail="TASK_COLLISION: Task ID already exists")

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
        raise HTTPException(500, detail=f"Write failed: {e}")

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
    # Validate task_id format
    if ".." in task_id or "/" in task_id:
        raise HTTPException(400, detail="Invalid task ID")

    # Search for task state in telemetry
    state = "unknown"
    last_event = None
    result_summary = None

    # Check multiple telemetry sources
    telemetry_files = [
        Path("/Users/icmini/0luka/observability/telemetry/bridge_consumer.latest.json"),
        Path("/Users/icmini/0luka/observability/telemetry/executor_lisa.latest.json"),
    ]

    for telem_file in telemetry_files:
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
