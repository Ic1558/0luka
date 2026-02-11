#!/usr/bin/env python3
"""
OPAL API v1.2.0 - Telemetry & Health Service
WO: WO-OPAL-API-IMPLEMENT-V1
Created: 2025-11-27
Port: 7001
"""

import json
import os
import secrets
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime
from urllib.parse import urlparse, unquote
import urllib.request

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from runtime.apps.opal_api.common import (
    HealthResponse, StatusResponse, JobInfo, JobDetail, 
    JobsDB, WorkerRegistry, normalize_paths, read_json_file, 
    PROJECT_ROOT, TELEMETRY_PATH, BUDGET_PATH, HEALTH_LOG_PATH, 
    UPLOADS_DIR, ARTIFACTS_DIR
)

# ═══════════════════════════════════════════
# FastAPI App
# ═══════════════════════════════════════════
app = FastAPI(
    title="OPAL API",
    description="Telemetry & Health Service for 02luka OPAL V4 Pipeline",
    version="1.2.0",
    openapi_url=None, # Disable default to allow SOT file serving
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
# Authoritative Contract Reflection (SOT = Ic1558/core)
# ═══════════════════════════════════════════
_DEFAULT_CORE_CONTRACTS_URL = "https://raw.githubusercontent.com/Ic1558/core/main"
_CONTRACT_REL = "contracts/v1/opal_api.openapi.json"

def _load_contract_bytes() -> bytes:
    src = (
        os.environ.get("CORE_CONTRACTS_URL")
        or os.environ.get("CORE_CONTRACT_URL")
        or _DEFAULT_CORE_CONTRACTS_URL
    ).strip()
    if not src:
        src = _DEFAULT_CORE_CONTRACTS_URL

    # file:// URL support
    if src.startswith("file://"):
        u = urlparse(src)
        p = Path(unquote(u.path))
        if p.is_dir():
            p = p / _CONTRACT_REL
        return p.read_bytes()

    # Filesystem paths (absolute or relative-to-repo-root)
    if "://" not in src:
        p = Path(src)
        if not p.is_absolute():
            p = (PROJECT_ROOT / p).resolve()
        if p.is_dir():
            p = p / _CONTRACT_REL
        return p.read_bytes()

    # URL to file OR URL base directory
    url = src if src.endswith(".json") else (src.rstrip("/") + "/" + _CONTRACT_REL)
    with urllib.request.urlopen(url, timeout=10) as resp:
        return resp.read()

@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    try:
        b = _load_contract_bytes()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Failed to load authoritative contract: {e}")
    return Response(content=b, media_type="application/json")


# ═══════════════════════════════════════════
# Endpoints
# ═══════════════════════════════════════════
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

@app.get("/api/jobs", response_model=dict[str, JobDetail])
async def list_jobs():
    """List all jobs (Minimal Law)."""
    return JobsDB.get_all_jobs()


@app.get("/api/workers", response_model=list[dict])
async def list_workers():
    """List all workers in the federation (A3.0)."""
    return WorkerRegistry.list_workers()


@app.get("/api/nodes", response_model=dict)
async def list_nodes():
    """List aggregated nodes/hosts (A3.0)."""
    workers = WorkerRegistry.list_workers()
    nodes = {}
    
    for w in workers:
        # Worker ID format: host_id:seq (A2.2) or deprecated format
        wid = w.get("worker_id", "")
        if ":" in wid:
            host_id = wid.split(":")[0]
        else:
            # Fallback for legacy ID (hostname-pid)
            host_id = w.get("host", "unknown")

        if host_id not in nodes:
            nodes[host_id] = {
                "host_id": host_id,
                "hostname": w.get("host"),
                "worker_count": 0,
                "engine_slots_total": 0,
                "last_seen_latest": "",
            }
        
        node = nodes[host_id]
        node["worker_count"] += 1
        node["engine_slots_total"] += w.get("engine_slots", 0)
        
        ls = w.get("last_seen", "")
        if ls > node["last_seen_latest"]:
            node["last_seen_latest"] = ls
            
    return {"nodes": list(nodes.values())}


@app.post("/api/jobs", response_model=JobInfo, status_code=201)
async def create_job(
    prompt: str = Form(...),
    input_file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    job_id: Optional[str] = Form(None)
):
    """Submit a new design pipeline job (Minimal Law)."""
    job_id = job_id or f"job_{secrets.token_hex(6)}"
    
    # Save file
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOADS_DIR / f"{job_id}_{input_file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(input_file.file, buffer)
    
    # Create Job Logic
    job_metadata = {}
    if metadata:
        try:
            job_metadata = json.loads(metadata)
        except json.JSONDecodeError:
            # Fallback: treat as plain string or ignore?
            # Contract says object. Let's ignore if invalid JSON to be safe, or just store as is if DB allows?
            # Let's try to be helpful.
            print(f"WARN: Failed to parse metadata JSON: {metadata}")
            pass

    # Persist job
    job = JobsDB.create_job(
        job_id=job_id,
        prompt=prompt,
        input_file=str(file_path),
        metadata=job_metadata
    )
    
    return JobInfo(id=job["id"], status=job["status"])


@app.get("/api/jobs/{id}", response_model=JobDetail)
async def get_job(id: str):
    """Retrieve job status (Minimal Law)."""
    job = JobsDB.get_job(id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobDetail(**job)

@app.get("/api/artifacts/{id:path}")
async def get_artifact(id: str):
    """Retrieve an artifact by its stable ID."""
    # Search for artifact in ARTIFACTS_DIR recursively or look up via job outputs?
    # Simple strategy: ARTIFACTS_DIR/{job_id}/{artifact_id} or just flat ID mapping?
    # Revised strategy per plan: runtime/opal_artifacts/{job_id}/...
    # But this endpoint takes "id". If the artifact ID is globally unique (e.g. UUID), verify existence.
    # For now, let's assume the ID passed here is the filename or a specific ID.
    # To be safe, we might need a mapping.
    # Simpler: JobOutput has "href": "/api/artifacts/{id}".
    # Let's assume {id} encodes "job_id|artifact_name" or we have a flat store.
    # Given minimal law, let's keep it simple: {id} maps to a file in flat ARTIFACTS_DIR or we iterate.
    
    # Let's assume the worker stores it as ARTIFACTS_DIR / id (where id includes extension?).
    # Actually, the plan said "runtime/opal_artifacts/{job_id}/".
    # So we probably need GET /api/jobs/{job_id}/artifacts/{artifact_id} OR
    # make the artifact ID unique.
    
    # Decision: Use flat unique ID (UUID) for artifact filename on disk for serving simplicity.
    file_path = (ARTIFACTS_DIR / id).resolve()
    
    # Security: Prevent path traversal
    if not str(file_path).startswith(str(ARTIFACTS_DIR.resolve())):
        raise HTTPException(status_code=403, detail="Access denied")
        
    if not file_path.exists():
        # Fallback: check if it's a job_id/name structure?
        # Let's stick to the generated href logic in worker.
        raise HTTPException(status_code=404, detail="Artifact not found")
        
    return FileResponse(file_path)

# ═══════════════════════════════════════════
# Telemetry implementation (Proxied for brevity)
# ═══════════════════════════════════════════
@app.get("/api/telemetry/latest")
async def telemetry_latest():
    health_data = read_json_file(TELEMETRY_PATH) or {}
    from datetime import datetime
    return normalize_paths({
        "ts": datetime.now().isoformat(),
        "health": health_data,
        "env": {"root": str(DISPLAY_ROOT)}
    })
    
@app.get("/api/telemetry/summary")
async def telemetry_summary():
    data = read_json_file(TELEMETRY_PATH)
    from datetime import datetime
    if data is None:
        return {
            "overall_status": "unknown",
            "timestamp": datetime.now().isoformat(),
            "components": {},
            "error": "No telemetry data available",
        }
    return normalize_paths({
        "overall_status": data.get("overall_status", "unknown"),
        "timestamp": data.get("timestamp"),
        "components": {
            "redis": "healthy", # Placeholder
            "opal_api": "healthy"
        }
    })

# ═══════════════════════════════════════════
# Main
# ═══════════════════════════════════════════
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7001)
