from fastapi import APIRouter, HTTPException
from ..models import CommandSubmission, TaskSpec, RiskLevel, TaskOperation
from ..utils.rw_guard import assert_write_scope, assert_safe_filename, INTERFACE_ROOT
from datetime import datetime, timezone
import random
import string
import yaml
from pathlib import Path

router = APIRouter()

def generate_task_id() -> str:
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d_%H%M%S")
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"task_{ts}_{rand}"

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def normalize_task(submission: CommandSubmission) -> TaskSpec:
    # Logic to convert Natural Language -> Structured Task
    # For Phase 0, we trust 'structured_override' or return a dummy OP
    
    ops = []
    if submission.structured_override:
         # TODO: Validate override against schema
         pass
         
    # Fallback/Dummy logic for demo
    if not ops:
        ops = [TaskOperation(id="op_1", tool="unknown", params={"raw": submission.raw_input}, risk_hint=RiskLevel.HIGH)]
        
    return TaskSpec(
        task_id=generate_task_id(),
        author="gmx", # INJECTED
        intent=submission.raw_input,
        operations=ops,
        created_at_utc=now_utc_iso()
    )

@router.post("/preview")
async def preview_command(submission: CommandSubmission):
    normalized = normalize_task(submission)
    return {
        "task": normalized,
        "risk": "high" if any(op.risk_hint == RiskLevel.HIGH for op in normalized.operations) else "low",
        "diff_preview": "TODO: git diff simulation"
    }

@router.post("/submit")
async def submit_command(submission: CommandSubmission):
    task = normalize_task(submission)
    
    # 1. Generate Filename
    filename = f"{task.task_id}.yaml"
    assert_safe_filename(filename)
    
    # 2. Assert Path Scope
    target_path = INTERFACE_ROOT / "inbox" / filename
    assert_write_scope(target_path)
    
    # 3. Write Once (No Overwrite)
    if target_path.exists():
        raise HTTPException(status_code=409, detail="Task ID collision")
    
    # 4. Write
    try:
        # Pydantic -> Dict -> YAML
        # Use mode='json' to ensure Enums are serialized to strings
        data = task.model_dump(mode='json')
        with open(target_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)
    except Exception as e:
        # Cleanup empty file if write failed
        if target_path.exists() and target_path.stat().st_size == 0:
            target_path.unlink()
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"status": "ok", "task_id": task.task_id, "path": str(target_path)}
