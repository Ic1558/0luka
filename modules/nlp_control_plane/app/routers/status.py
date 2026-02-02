"""
Status Router - System Health Endpoint
======================================
COPY EXACT from tools/web_bridge/routers/status.py
"""

from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
import os

from ...core.contracts import StatusResponse, HealthStatus, StalenessMetric, AgentValues

router = APIRouter()

PROJECT_ROOT = Path(os.environ.get("LUKA_ROOT", "/Users/icmini/0luka")).resolve()
OBSERVABILITY_ROOT = (PROJECT_ROOT / "observability/telemetry").resolve()

def load_latest_json(stem: str) -> dict:
    try:
        path = OBSERVABILITY_ROOT / f"{stem}.latest.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text())
    except Exception:
        return {}

def get_staleness() -> StalenessMetric:
    # Try to load real staleness data if available
    # For now, we mock/infer from files, or read a specific metric file
    # Assuming there's a 'staleness_guard.state.json' or similar.
    # If not, return default safe values.
    return StalenessMetric(
        targets_ok=0,
        targets_total=0,
        worst_age_seconds=0
    )

@router.get("/status", response_model=StatusResponse)
async def get_system_status():
    health_data = load_latest_json("health")
    agents_data = {}

    # Check agents
    for agent in [AgentValues.LIAM, AgentValues.LISA]:
        agent_health = load_latest_json(agent)
        # Simplified logic: if file exists and recent -> active
        agents_data[agent] = "active" if agent_health else "unknown" # Todo: check timestamp

    sot_age = health_data.get("sot_age_seconds", 0)

    return StatusResponse(
        health=HealthStatus.OK if sot_age < 300 else HealthStatus.DEGRADED,
        sot_age_seconds=sot_age,
        staleness=get_staleness(),
        agents=agents_data,
        last_error=health_data.get("last_error")
    )

@router.get("/telemetry")
async def get_telemetry_stream(limit: int = 50, agent: str = None):
    # READ-ONLY: Stream lines from jsonl
    # TODO: Implement strict file reading
    return {"status": "not_implemented_yet", "note": "Safe implementation pending"}
