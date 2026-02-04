#!/usr/bin/env python3
"""
OPAL API v1 - Telemetry & Health Service
WO: WO-OPAL-API-IMPLEMENT-V1
Created: 2025-11-27
Port: 7001

Endpoints:
- GET /api/health          - Basic health check
- GET /api/telemetry/health - Full health check JSON
- GET /api/telemetry/summary - Slim summary for UI
- GET /api/budget          - Dev lane budget info
- GET /api/status          - Quick status (for other health checks)
"""

import json
import os
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ═══════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════
PROJECT_ROOT = Path(os.environ.get("LUKA_BASE", "/Users/icmini/0luka"))
TELEMETRY_PATH = PROJECT_ROOT / "observability" / "telemetry" / "health.latest.json"
BUDGET_PATH = PROJECT_ROOT / "observability" / "finance" / "budget.json"
HEALTH_LOG_PATH = PROJECT_ROOT / "observability" / "logs" / "health.log"
DISPLAY_ROOT = PROJECT_ROOT
DISPLAY_ROOT_STR = str(DISPLAY_ROOT)
DISPLAY_ROOT_REF = "${ROOT}"

# ═══════════════════════════════════════════
# FastAPI App
# ═══════════════════════════════════════════
app = FastAPI(
    title="OPAL API",
    description="Telemetry & Health Service for 02luka OPAL V4 Pipeline",
    version="1.0.0",
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════
# Authoritative Contract Reflection
# ═══════════════════════════════════════════
CONTRACT_PATH = PROJECT_ROOT / "core" / "contracts" / "v1" / "opal_api.openapi.json"

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    if CONTRACT_PATH.exists():
        with open(CONTRACT_PATH, "r") as f:
            return json.load(f)
    return app.openapi()

app.openapi = custom_openapi

# ═══════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════
def read_json_file(path: Path) -> Optional[dict]:
    """Safely read JSON file, return None if not found or invalid."""
    try:
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[OPAL API] Error reading {path}: {e}")
    return None


def get_last_log_line(path: Path) -> Optional[str]:
    """Get the last line from a log file."""
    try:
        if path.exists():
            with open(path, "r") as f:
                lines = f.readlines()
                return lines[-1].strip() if lines else None
    except IOError:
        pass
    return None


def normalize_paths(obj: Any) -> Any:
    """Normalize absolute root paths for display without mutating source data."""
    if isinstance(obj, dict):
        return {k: normalize_paths(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_paths(v) for v in obj]
    if isinstance(obj, str):
        return obj.replace(DISPLAY_ROOT_STR, DISPLAY_ROOT_REF)
    return obj


# ═══════════════════════════════════════════
# Models
# ═══════════════════════════════════════════
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    service: str = "opal_api"
    version: str = "1.0.0"


class StatusResponse(BaseModel):
    status: str
    uptime: str = "running"
    port: int = 7001


class JobStatus(str):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobOutput(BaseModel):
    path: str
    kind: str


class JobError(BaseModel):
    message: str


class JobInfo(BaseModel):
    id: str
    status: str


class JobDetail(BaseModel):
    id: str
    status: str
    outputs: Optional[list[JobOutput]] = None
    error: Optional[JobError] = None


# ═══════════════════════════════════════════
# Persistence (JobsDB)
# ═══════════════════════════════════════════
JOBS_DB_PATH = PROJECT_ROOT / "observability" / "jobs_db.json"
UPLOADS_DIR = PROJECT_ROOT / "observability" / "uploads"

class JobsDB:
    @staticmethod
    def _read() -> dict[str, Any]:
        if not JOBS_DB_PATH.exists():
            return {}
        try:
            with open(JOBS_DB_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    @staticmethod
    def _write(data: dict[str, Any]):
        JOBS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(JOBS_DB_PATH, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def create_job(cls, job_id: str, prompt: str, input_file: str) -> dict:
        db = cls._read()
        job = {
            "id": job_id,
            "prompt": prompt,
            "input_file": input_file,
            "status": JobStatus.QUEUED,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "outputs": [],
            "error": None
        }
        db[job_id] = job
        cls._write(db)
        return job

    @classmethod
    def get_job(cls, job_id: str) -> Optional[dict]:
        db = cls._read()
        return db.get(job_id)


# ═══════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════
@app.post("/api/jobs", response_model=JobInfo, status_code=201)
async def create_job(
    prompt: str = Form(...),
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None)
):
    """Submit a new design pipeline job (Minimal Law)."""
    job_id = f"job_{secrets.token_hex(6)}"
    
    # Save file
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOADS_DIR / f"{job_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Persist job
    job = JobsDB.create_job(
        job_id=job_id,
        prompt=prompt,
        input_file=str(file_path)
    )
    
    return JobInfo(id=job["id"], status=job["status"])


@app.get("/api/jobs/{id}", response_model=JobDetail)
async def get_job(id: str):
    """Retrieve job status (Minimal Law)."""
    job = JobsDB.get_job(id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobDetail(**job)


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Basic health check endpoint."""
    return HealthResponse(
        status="ok",
        timestamp=datetime.now().isoformat(),
    )


@app.get("/health", response_model=HealthResponse)
async def health_alias():
    """Alias for /api/health to reduce 404 noise."""
    return await health_check()


@app.get("/api/status", response_model=StatusResponse)
async def quick_status():
    """Quick status for other health checks (avoids recursion)."""
    return StatusResponse(status="ok")


@app.get("/api/telemetry/latest")
async def telemetry_latest():
    """Returns the latest consolidated telemetry state."""
    health_data = read_json_file(TELEMETRY_PATH) or {}
    # Gathers other pointers if available
    return normalize_paths({
        "ts": datetime.now().isoformat(),
        "health": health_data,
        "env": {
            "root": str(DISPLAY_ROOT),
        }
    })


@app.get("/api/telemetry/health")
async def telemetry_health():
    """Full health check JSON from health_check_latest.json."""
    data = read_json_file(TELEMETRY_PATH)
    
    if data is None:
        return normalize_paths({
            "status": "unknown",
            "error": "health_check_latest.json not found or invalid",
            "source": "file",
            "path": str(TELEMETRY_PATH),
        })
    
    # Add source metadata
    data["source"] = "file"
    data["api_timestamp"] = datetime.now().isoformat()
    return normalize_paths(data)


@app.get("/api/telemetry/summary")
async def telemetry_summary():
    """Slim summary view for UI dashboard."""
    data = read_json_file(TELEMETRY_PATH)
    
    if data is None:
        return {
            "overall_status": "unknown",
            "timestamp": datetime.now().isoformat(),
            "components": {},
            "error": "No telemetry data available",
        }
    
    # Extract key fields for summary
    summary = {
        "overall_status": data.get("overall_status", "unknown"),
        "timestamp": data.get("timestamp", datetime.now().isoformat()),
        "api_timestamp": datetime.now().isoformat(),
        "components": {
            "redis": "healthy" if "redis" in str(data.get("checks", [])) else "unknown",
            "opal_api": "healthy",  # We're responding, so we're healthy
            "launchagents": data.get("agents", {}),
        },
        "metrics": data.get("metrics", {}),
        "auto_restart_enabled": data.get("auto_restart_enabled", False),
    }
    return normalize_paths(summary)


@app.get("/api/budget")
async def get_budget():
    """Dev lane budget information."""
    data = read_json_file(BUDGET_PATH)
    
    if data is None:
        # Return default budget structure if file doesn't exist
        return {
            "status": "default",
            "message": "Budget file not found, using defaults",
            "budget": {
                "daily_limit_usd": 5.0,
                "used_today_usd": 0.0,
                "remaining_usd": 5.0,
                "reset_time": "00:00 UTC",
            },
            "lanes": {
                "free": {"enabled": True, "priority": 1},
                "gemini": {"enabled": True, "priority": 2, "cost_per_call": 0.001},
                "gpt4": {"enabled": True, "priority": 3, "cost_per_call": 0.03},
            },
        }
    
    data["status"] = "loaded"
    data["api_timestamp"] = datetime.now().isoformat()
    return normalize_paths(data)


@app.get("/api/telemetry/log")
async def telemetry_log():
    """Get recent health check log entries."""
    log_path = HEALTH_LOG_PATH
    
    try:
        if log_path.exists():
            with open(log_path, "r") as f:
                lines = f.readlines()
                # Return last 20 lines
                recent = lines[-20:] if len(lines) > 20 else lines
                recent_entries = [normalize_paths(line.strip()) for line in recent]
                return {
                    "status": "ok",
                    "total_entries": len(lines),
                    "recent_entries": recent_entries,
                }
    except IOError as e:
        return {"status": "error", "error": str(e)}
    
    return {"status": "empty", "recent_entries": []}


# ═══════════════════════════════════════════
# Root
# ═══════════════════════════════════════════
@app.get("/")
async def root():
    """API root with available endpoints."""
    return {
        "service": "OPAL API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "/api/health": "Basic health check",
            "/api/status": "Quick status",
            "/api/telemetry/health": "Full health telemetry",
            "/api/telemetry/latest": "Latest consolidated telemetry",
            "/api/telemetry/summary": "Summary for UI",
            "/api/telemetry/log": "Recent log entries",
            "/api/telemetry/log": "Recent log entries",
            "/api/budget": "Dev lane budget info",
            "TASK_SYSTEM": "http://127.0.0.1:8080/api/tasks/list (0luka Native)",
        },
    }


# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7001)
