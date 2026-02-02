from pydantic import BaseModel, Field, constr
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
