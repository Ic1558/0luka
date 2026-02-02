"""
NLP Control Plane Contracts (Models)
====================================
Pydantic models for API requests and responses.

COPY EXACT from tools/web_bridge/models.py + routers/chat.py models.
"""

from pydantic import BaseModel, Field
from typing import Literal, Dict, Any, List, Optional
from datetime import datetime

from enum import Enum

# --- Enums ---
class AgentValues(str, Enum):
    LIAM = "liam"
    LISA = "lisa"
    GMX = "gmx"
    VERA = "vera"

class HealthStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    DEGRADED = "degraded"

class RiskLevel(str, Enum):
    LOW = "low"
    HIGH = "high"

class GateVerdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    MISSING = "MISSING"

# --- Models ---

class StalenessMetric(BaseModel):
    targets_ok: int
    targets_total: int
    worst_age_seconds: int

class StatusResponse(BaseModel):
    health: HealthStatus
    sot_age_seconds: Optional[int]
    staleness: StalenessMetric
    agents: Dict[str, str] = Field(default_factory=dict)
    last_error: Optional[str] = None

class TaskOperation(BaseModel):
    id: str
    tool: str
    params: Dict[str, Any]
    risk_hint: RiskLevel = RiskLevel.LOW

class CommandContext(BaseModel):
    page: Optional[str] = None
    selection: Optional[str] = None

class CommandSubmission(BaseModel):
    """
    Contract for Client -> Server.
    Frontend CANNOT set author or task_id.
    """
    raw_input: str
    structured_override: Optional[Dict[str, Any]] = None
    context: Optional[CommandContext] = None

class TaskSpec(BaseModel):
    """
    Contract for Server -> Filesystem.
    Fully hydrated task object.
    """
    task_id: str = Field(description="Server-generated: task_YYYYMMDD_HHMMSS_RAND6")
    author: Literal["gmx"] = Field(default="gmx", description="Enforced by Server")
    intent: str
    operations: List[TaskOperation]
    created_at_utc: str

    # Forensic / Routing fields
    lane: Literal["task", "ops"] = "task"
    reply_to: str = "interface/outbox/tasks"

class GateItem(BaseModel):
    task_id: str
    intent: str
    author: str
    ts_utc: str
    path: str
    vera_verdict: GateVerdict = GateVerdict.MISSING
    risk_level: str = "unknown"

# --- Chat-specific Models (from routers/chat.py) ---

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
