#!/usr/bin/env python3
"""
OPAL Massing Engine Worker (Adapter)
Executes nano_banana_engine.py with strict isolation and provenance tracking.
"""
import time
import json
import hashlib
import subprocess
import shutil
import fcntl
from pathlib import Path
from datetime import datetime
from typing import Set
import logging
import socket
import os

from runtime.apps.opal_api.common import (
    JobsDB, JobStatus, JobOutput, 
    PROJECT_ROOT, ARTIFACTS_DIR, JOBS_DB_PATH
)
from core.enforcement import RuntimeEnforcer, PermissionDenied

def _collect_candidate_paths(job: dict) -> list[str]:
    """
    Deep scan for file paths, catching nested keys and dangerous patterns.
    """
    candidates = set()
    
    def _scan(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                # Check Key hints
                if k in ("input_path", "output_path", "workdir", "cwd", "script_path", "binary_path", "mounts", "files"):
                    if isinstance(v, str): candidates.add(v)
                    elif isinstance(v, list): 
                        for x in v: 
                            if isinstance(x, str): candidates.add(x)
                
                # Check Value hints (recursion)
                _scan(v)
        elif isinstance(obj, list):
            for item in obj:
                _scan(item)
        elif isinstance(obj, str):
            # Heuristic detection of path-like strings
            # 1. Absolute paths (*nix)
            if obj.startswith("/"): candidates.add(obj)
            # 2. Home dir
            if obj.startswith("~"): candidates.add(obj)
            # 3. Traversal / Relative
            if "../" in obj or "./" in obj: candidates.add(obj)
            # 4. Windows / URI
            # Catch C:\, C:/, D:\ etc.
            if len(obj) > 1 and obj[1] == ":": candidates.add(obj)
            # Catch UNC \\server\share or //server/share
            if obj.startswith("\\\\") or obj.startswith("//"): candidates.add(obj)
            # Catch file:// scheme
            if obj.startswith("file://"): candidates.add(obj)

    _scan(job)
    
    norm = []
    base_dir = PROJECT_ROOT # Resolve relative paths against Root (conservative)
    
    for p in candidates:
        try:
            # Handle file://
            if p.startswith("file://"): p = p[7:]
            
            path_obj = Path(p).expanduser()
            if not path_obj.is_absolute():
                path_obj = base_dir / path_obj
                
            norm.append(str(path_obj.resolve(strict=False)))
        except Exception:
            # If malformed, keep raw to potentially trigger deny if strictly matched
            norm.append(p)
            
    return list(set(norm))

# Phase 6A.4: Observability
# Configure structured logging (JSON-like)
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "worker": "%(worker_id)s", "event": "%(message)s"}'
)
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
logger = logging.getLogger("opal_worker")
# Inject worker_id into logs
old_factory = logging.getLogRecordFactory()
def record_factory(*args, **kwargs):
    record = old_factory(*args, **kwargs)
    record.worker_id = WORKER_ID
    return record
logging.setLogRecordFactory(record_factory)

ENGINE_SCRIPT = PROJECT_ROOT / "modules/studio/features/nano_banana_engine.py"
MOCK_ENGINE_SCRIPT = PROJECT_ROOT / "modules/studio/features/mock_engine_v1.py"
STUDIO_OUTPUT_DIR = PROJECT_ROOT / "modules/studio/outputs"
LOCK_FILE = PROJECT_ROOT / "modules/studio/.opal_lock"

def calculate_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def calculate_file_sha256(file_path: Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_canonical_input_checksum(job: dict, engine_name: str) -> str:
    """Calculates SHA256 of the canonical inputs."""
    # Canonical inputs: prompt + file_checksum (if any) + engine info
    canonical_data = {
        "prompt": job.get("prompt", ""),
        "engine": engine_name,
        "version": "v1" # Todo: get real version
    }
    return calculate_sha256(json.dumps(canonical_data, sort_keys=True).encode("utf-8"))

def acquire_lock():
    """Acquires an exclusive lock to prevent concurrent engine runs."""
    lock_fd = open(LOCK_FILE, 'w')
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except IOError:
        lock_fd.close()
        return None

def release_lock(lock_fd):
    """Releases the lock."""
    if lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()

def list_studio_outputs() -> Set[Path]:
    if not STUDIO_OUTPUT_DIR.exists():
        return set()
    return set(STUDIO_OUTPUT_DIR.iterdir())

def run_massing_engine_adapter(job: dict) -> tuple[list[dict], dict]:
    """
    Executes the Massing Engine with isolation.
    Returns (outputs, provenance).
    """
    # ═══════════════════════════════════════════
    # WORKER TOOL GATE
    # ═══════════════════════════════════════════
    try:
        candidate_paths = _collect_candidate_paths(job)
        
        # Define Scope: Allowed paths for Worker
        # Use .resolve() to ensure canonical paths for comparison
        safe_roots = [
            str((PROJECT_ROOT / "modules/studio").resolve()),
            str(ARTIFACTS_DIR.resolve()),
            str((PROJECT_ROOT / "runtime/opal_uploads").resolve()),
            str(Path("/tmp").resolve())
        ]
        
        # Check all collected paths against Enforcer
        # We treat any path access as a generic "read_file" check for now to validate scope
        for path in candidate_paths:
            RuntimeEnforcer.enforce_tool_access(
                role="worker",
                tool="read_file", 
                args={"path": path},
                scope={"allowed_paths": safe_roots}
            )
            
        # Check Subprocess Execution Capability
        # This checks headers/flags but not specific paths (already checked above)
        RuntimeEnforcer.enforce_tool_access(
            role="worker",
            tool="subprocess",
            args={"job_id": job["id"], "engine": job.get("metadata", {}).get("engine")},
            scope={"allowed_paths": safe_roots} 
        )
            
    except PermissionDenied as e:
         logger.warning(f"[Worker Gate] DENIED: {e}")
         # Fail the job immediately
         return [], {
             "engine": "opal_security_gate",
             "version": "1.0",
             "error": str(e),
             "input_checksum": "00000000"
         }
    # ═══════════════════════════════════════════

    # 6B-lite: Engine Agnosticism
    engine_name = job.get("metadata", {}).get("engine", "nano_banana_engine")
    
    if engine_name == "mock_engine_v1":
        target_script = MOCK_ENGINE_SCRIPT
        print(f"[Worker] Processing job {job['id']} with MOCK ENGINE...")
    else:
        # Default / Fallback
        target_script = ENGINE_SCRIPT
        engine_name = "nano_banana_engine" # Normalize
        print(f"[Worker] Processing job {job['id']} with Nano Banana...")
    
    # 1. Prepare Workspace
    STUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    job_artifacts_dir = ARTIFACTS_DIR / job["id"]
    job_artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Create Input JSON
    input_payload = {
        "job_id": job["id"],
        "parameters": {
            "prompt": job.get("prompt", ""),
            "control_weight": 0.9, # Default for now
            "denoising_strength": 0.5
        }
    }
    input_json_path = STUDIO_OUTPUT_DIR / f"input_{job['id']}.json"
    with open(input_json_path, 'w') as f:
        json.dump(input_payload, f)

    # 3. Snapshot & Lock
    lock_fd = acquire_lock()
    if not lock_fd:
        raise RuntimeError("Could not acquire engine lock. Another job is running.")
    
    try:
        pre_snapshot = list_studio_outputs()
        
        # 4. Execute
        # Typer collapses single-command apps, so 'activate' keyword is implicitly removed from CLI
        cmd = ["python3", str(target_script), str(input_json_path)]
        print(f"[Worker] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Engine failed: {result.stderr}")
            
        print(f"[Worker] Engine Output: {result.stdout}")

        # 5. Diff
        post_snapshot = list_studio_outputs()
        new_files = post_snapshot - pre_snapshot
        
        # Filter strictly for result manifest and artifacts if engine produces them
        # Nano Banana produces result_{job_id}.json
        manifest_path = STUDIO_OUTPUT_DIR / f"result_{job['id']}.json"
        
        outputs = []
        if manifest_path in new_files:
            # Parse manifest if needed, or just trust the new files.
            # Start by moving ALL new files (except input.json) to artifact dir
            for file_path in new_files:
                if file_path == input_json_path:
                    continue
                
                # Move to permanent storage
                dest_path = job_artifacts_dir / file_path.name
                shutil.move(str(file_path), str(dest_path))
                
                # Metadata
                sha256 = calculate_file_sha256(dest_path)
                
                # Determine mime type (simple check)
                mime = "application/octet-stream"
                if dest_path.suffix == ".json": mime = "application/json"
                elif dest_path.suffix == ".png": mime = "image/png"
                elif dest_path.suffix == ".obj": mime = "model/obj"
                elif dest_path.suffix == ".txt": mime = "text/plain"
                
                serve_id = f"{job['id']}/{dest_path.name}"
                
                outputs.append({
                    "id": f"artifact_{calculate_sha256(serve_id.encode())[:8]}",
                    "name": dest_path.name,
                    "kind": "artifact", # Could refine based on extension
                    "mime": mime,
                    "sha256": sha256,
                    "href": f"/api/artifacts/{serve_id}"
                })
        else:
             # If no manifest found but success, maybe check other new files?
             # For now, strict: if no result_{job_id}.json and return 0, warn?
             pass

    finally:
        # 6. Cleanup
        if input_json_path.exists():
            input_json_path.unlink()
        release_lock(lock_fd)

    provenance = {
        "engine": engine_name,
        "version": "1.0", # Placeholder
        "input_checksum": get_canonical_input_checksum(job, engine_name)
    }
    
    return outputs, provenance

def recover_crashed_jobs():
    """
    Scans for jobs left in RUNNING state from a previous worker crash
    and transitions them to FAILED.
    """
    logger.info("Running crash recovery scan...")
    all_jobs = JobsDB.get_all_jobs()
    zombies_found = 0
    
    for job_id, job in all_jobs.items():
        if job["status"] == JobStatus.RUNNING:
            logger.warning(f"Found zombie job {job_id}. Marking FAILED.")
            JobsDB.update_job(job_id, {
                "status": JobStatus.FAILED,
                "error": {"message": "worker_crash"},
                "completed_at": datetime.now().isoformat()
            })
            zombies_found += 1
            
    if zombies_found > 0:
        logger.info(f"Recovered {zombies_found} zombie jobs.")
    else:
        logger.info("No zombie jobs found.")

def run_job_gc():
    """
    Garbage Collects terminal jobs older than retention threshold.
    """
    # Retention: 24 hours
    RETENTION_SECONDS = 24 * 3600
    now = datetime.now()
    cutoff_time = now.timestamp() - RETENTION_SECONDS
    
    all_jobs = JobsDB.get_all_jobs()
    deleted_count = 0
    
    for job_id, job in list(all_jobs.items()):
        # Check if terminal
        if job["status"] not in [JobStatus.SUCCEEDED, JobStatus.FAILED]:
            continue
            
        # Check age based on completed_at or created_at or updated_at
        # Prefer completed_at, fallback to updated_at
        ref_time_str = job.get("completed_at") or job.get("updated_at")
        if not ref_time_str:
            continue
            
        try:
            ref_time = datetime.fromisoformat(ref_time_str).timestamp()
        except ValueError:
            continue
            
        if ref_time < cutoff_time:
            logger.info(f"GC: Deleting expired job {job_id}")
            # Delete artifacts
            artifact_dir = ARTIFACTS_DIR / job_id
            if artifact_dir.exists():
                shutil.rmtree(artifact_dir)
            
            # Delete record
            JobsDB.delete_job(job_id)
            deleted_count += 1
            
    if deleted_count > 0:
        logger.info(f"GC: Purged {deleted_count} jobs.")

def count_running_jobs() -> int:
    all_jobs = JobsDB.get_all_jobs()
    return sum(1 for job in all_jobs.values() if job["status"] == JobStatus.RUNNING)

def main():
    logger.info("Starting OPAL Massing Engine Worker (Real Adapter)...")
    
    # Phase 6A.2: Crash Recovery
    recover_crashed_jobs()
    
    logger.info(f"Polling JobsDB at {JOBS_DB_PATH}...")
    
    MAX_RUNNING_JOBS = 1
    loop_count = 0
    while True:
        try:
            # Phase 6A.1: GC Tick (every 100 loops ~ 200s)
            loop_count += 1
            if loop_count % 100 == 0:
                 run_job_gc()

            # Phase 6A.3: Concurrency Guard
            if count_running_jobs() >= MAX_RUNNING_JOBS:
                # Backpressure: Skip dequeue
                time.sleep(2)
                continue

            job = JobsDB.get_next_queued_job()
            if job:
                logger.info(f"Picked up job {job['id']}")
                JobsDB.update_job(job["id"], {
                    "status": JobStatus.RUNNING,
                    "started_at": datetime.now().isoformat()
                })
                
                try:
                    outputs, provenance = run_massing_engine_adapter(job)
                    JobsDB.update_job(job["id"], {
                        "status": JobStatus.SUCCEEDED,
                        "completed_at": datetime.now().isoformat(),
                        "outputs": outputs,
                        "run_provenance": provenance
                    })
                    logger.info(f"Job {job['id']} SUCCEEDED")
                except Exception as e:
                    logger.error(f"Job {job['id']} FAILED: {e}")
                    JobsDB.update_job(job["id"], {
                        "status": JobStatus.FAILED,
                        "completed_at": datetime.now().isoformat(),
                        "error": {"message": str(e)}
                    })
            else:
                time.sleep(2)
        except KeyboardInterrupt:
            logger.info("Stopping...")
            break
        except Exception as e:
            logger.error(f"Error in loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
