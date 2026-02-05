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

import threading

from runtime.apps.opal_api.common import (
    JobsDB, JobStatus, JobOutput, 
    PROJECT_ROOT, ARTIFACTS_DIR, JOBS_DB_PATH, UPLOADS_DIR,
    WorkerRegistry, OPAL_HEARTBEAT_INTERVAL_SECS, OPAL_WORKER_TTL_SECS,
    JobLeaseStore, OPAL_LEASE_TTL_SECS, OPAL_LEASE_RENEW_SECS,
    JobAttemptStore, OPAL_MAX_RETRIES, OPAL_RETRY_BACKOFFS, JOBS_DB_LOCK_PATH, _exclusive_lock, _atomic_write_json,
    TelemetryLogger
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
# ═══════════════════════════════════════════
# Phase A1: Worker Identity & Concurrency Control
# ═══════════════════════════════════════════
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
HOSTNAME = socket.gethostname()
WORKER_INDEX = os.environ.get("WORKER_INDEX")
_HB_LAST = 0.0

logger = logging.getLogger("opal_worker")
# Inject worker_id into logs
old_factory = logging.getLogRecordFactory()
def record_factory(*args, **kwargs):
    record = old_factory(*args, **kwargs)
    record.worker_id = WORKER_ID
    return record
logging.setLogRecordFactory(record_factory)

def _heartbeat_tick(force: bool = False) -> None:
    global _HB_LAST
    now = time.monotonic()
    if force or (now - _HB_LAST) >= OPAL_HEARTBEAT_INTERVAL_SECS:
        # A2: Out-of-band Heartbeat
        slots = int(os.environ.get("OPAL_ENGINE_SLOTS", "1"))
        meta = {"pid": os.getpid()}
        if WORKER_INDEX:
            meta["worker_index"] = str(WORKER_INDEX)
            
        WorkerRegistry.upsert_heartbeat(
            worker_id=WORKER_ID,
            host=HOSTNAME,
            engine_slots=slots,
            meta=meta
        )
        # Opportunistic stale cleanup
        WorkerRegistry.prune_stale()
        _HB_LAST = now

ENGINE_SCRIPT = PROJECT_ROOT / "modules/studio/features/nano_banana_engine.py"
MOCK_ENGINE_SCRIPT = PROJECT_ROOT / "modules/studio/features/mock_engine_v1.py"
STUDIO_OUTPUT_DIR = PROJECT_ROOT / "modules/studio/outputs"

# A1: Engine Semaphore (Replaces Global .opal_lock)
# Default 1 slot per worker to be safe, unless OPAL_ENGINE_SLOTS > 1
class EngineSemaphore:
    def __init__(self, root_dir: Path, slots: int):
        self.root_dir = root_dir
        self.slots = max(1, int(slots))
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self._fds = []

    def acquire(self) -> int:
        """Attempts to acquire a slot. Returns slot_index or None."""
        for i in range(self.slots):
            p = self.root_dir / f"slot_{i}.lock"
            # Open with mode 666 so distinct users (if any) can read/write. 
            # But mostly same user.
            try:
                fd = os.open(str(p), os.O_CREAT | os.O_RDWR, 0o644)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._fds.append(fd)
                return i
            except (IOError, BlockingIOError):
                # Slot taken
                continue
        return None

    def release(self):
        for fd in self._fds:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            except Exception:
                pass
        self._fds = []

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

def list_studio_outputs() -> Set[Path]:
    if not STUDIO_OUTPUT_DIR.exists():
        return set()
    return set(STUDIO_OUTPUT_DIR.iterdir())

def run_massing_engine_adapter(job: dict, semaphore: EngineSemaphore) -> tuple[list[dict], dict]:
    """
    Executes the Massing Engine with isolation + semaphore.
    """
    # ═══════════════════════════════════════════
    # WORKER TOOL GATE
    # ═══════════════════════════════════════════
    try:
        candidate_paths = _collect_candidate_paths(job)
        
        # Define Scope: Allowed paths for Worker
        safe_roots = [
            str((PROJECT_ROOT / "modules/studio").resolve()),
            str(ARTIFACTS_DIR.resolve()),
            str(UPLOADS_DIR.resolve()),
            str(Path("/tmp").resolve())
        ]
        
        for path in candidate_paths:
            RuntimeEnforcer.enforce_tool_access(
                role="worker",
                tool_name="read_file", 
                args={"path": path},
                scope={"allowed_paths": safe_roots}
            )
            
        RuntimeEnforcer.enforce_tool_access(
            role="worker",
            tool_name="subprocess",
            args={"job_id": job["id"], "engine": job.get("metadata", {}).get("engine")},
            scope={"allowed_paths": safe_roots} 
        )
            
    except PermissionDenied as e:
         logger.warning(f"[Worker Gate] DENIED: {e}")
         raise RuntimeError(f"Security Gate Denial: {e}")

    # 6B-lite: Engine Agnosticism
    engine_name = job.get("metadata", {}).get("engine", "nano_banana_engine")
    
    if engine_name == "mock_engine_v1":
        target_script = MOCK_ENGINE_SCRIPT
        print(f"[Worker] Processing job {job['id']} with MOCK ENGINE...")
    else:
        target_script = ENGINE_SCRIPT
        engine_name = "nano_banana_engine"
        print(f"[Worker] Processing job {job['id']} with Nano Banana...")
    
    # 1. Prepare Workspace
    # A2.1: Increment attempt counter for this execution
    current_attempt = JobAttemptStore.increment_attempt(job["id"])
    
    STUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    job_artifacts_dir = ARTIFACTS_DIR / job["id"] / f"attempt_{current_attempt}"
    job_artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    input_payload = {
        "job_id": job["id"],
        "parameters": {
            "prompt": job.get("prompt", ""),
            "control_weight": 0.9,
            "denoising_strength": 0.5
        }
    }
    input_json_path = STUDIO_OUTPUT_DIR / f"input_{job['id']}.json"
    with open(input_json_path, 'w') as f:
        json.dump(input_payload, f)

    # 3. Semaphore Lock Check
    # We enter this function assuming we hold the Job Lease, but now we need the Engine Slot.
    slot = semaphore.acquire()
    wait_time = 0
    while slot is None:
        if wait_time > 60: # Avoid infinite hang
             raise RuntimeError("Timeout waiting for Engine Slot.")
        time.sleep(1)
        wait_time += 1
        slot = semaphore.acquire()

    logger.info(f"Acquired Engine Slot {slot}")
    
    try:
        pre_snapshot = list_studio_outputs()
        
        # 4. Execute
        cmd = ["python3", str(target_script), str(input_json_path)]
        print(f"[Worker] Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Engine failed: {result.stderr}")
            
        print(f"[Worker] Engine Output: {result.stdout}")

        # 5. Diff
        post_snapshot = list_studio_outputs()
        new_files = post_snapshot - pre_snapshot
        
        manifest_path = STUDIO_OUTPUT_DIR / f"result_{job['id']}.json"
        
        outputs = []
        if manifest_path in new_files:
            for file_path in new_files:
                if file_path == input_json_path:
                    continue
                
                dest_path = job_artifacts_dir / file_path.name
                shutil.move(str(file_path), str(dest_path))
                
                sha256 = calculate_file_sha256(dest_path)
                
                mime = "application/octet-stream"
                if dest_path.suffix == ".json": mime = "application/json"
                elif dest_path.suffix == ".png": mime = "image/png"
                elif dest_path.suffix == ".obj": mime = "model/obj"
                elif dest_path.suffix == ".txt": mime = "text/plain"
                
                serve_id = f"{job['id']}/{dest_path.name}"
                
                outputs.append({
                    "id": f"artifact_{calculate_sha256(serve_id.encode())[:8]}",
                    "name": dest_path.name,
                    "kind": "artifact",
                    "mime": mime,
                    "sha256": sha256,
                    "href": f"/api/artifacts/{serve_id}"
                })
        
    finally:
        # 6. Cleanup
        if input_json_path.exists():
            input_json_path.unlink()
        semaphore.release()
        logger.info(f"Released Engine Slot {slot}")

    provenance = {
        "engine": engine_name,
        "version": "1.0",
        "input_checksum": get_canonical_input_checksum(job, engine_name)
    }
    
    return outputs, provenance

def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

# ============================================================================
# LEGACY A1 RECOVERY (DEPRECATED - NOT CALLED)
# ============================================================================
# This function is preserved for reference only. It is NOT called in the
# worker loop. A2 lease-based recovery (reclaim_expired_leases) is now
# authoritative for all fault tolerance, including multi-host scenarios.
# ============================================================================

def recover_crashed_jobs():
    """
    A1: Scans for jobs left in RUNNING state by DEAD workers.
    """
    logger.info("Running A1 crash recovery scan (single-host PID check)...")
    all_jobs = JobsDB.get_all_jobs()
    zombies_found = 0
    
    for job_id, job in all_jobs.items():
        if job["status"] == JobStatus.RUNNING:
            wid = job.get("worker_id")
            if not wid:
                continue # Unclaimed?
                
            # Parse <hostname>-<pid>
            try:
                parts = wid.split("-")
                pid = int(parts[-1])
            except ValueError:
                continue
                
            # If PID is not alive, fail the job
            if not _pid_alive(pid):
                logger.warning(f"Found zombie job {job_id} from dead worker {wid}. Marking FAILED.")
                JobsDB.update_job(job_id, {
                    "status": JobStatus.FAILED,
                    "error": {"message": "worker_died_recovered_a1"},
                    "completed_at": datetime.now().isoformat()
                })
                zombies_found += 1
            
    if zombies_found > 0:
        logger.info(f"Recovered {zombies_found} zombie jobs.")

def reclaim_expired_leases():
    """
    A2-Phase2.1: Scans for expired leases and applies retry policy.
    Implements atomic 'Winner' logic + backoff to prevent storm.
    """
    expired_ids = JobLeaseStore.list_expired()
    if not expired_ids:
        return
        
    for job_id in expired_ids:
        # Fix#3: Atomic winner selection
        if not JobAttemptStore.try_mark_reclaimed(job_id, WORKER_ID, reason="lease_expired"):
            # Another worker already reclaimed this job
            continue
        
        # A2.1.1: Log reclaim winner
        prev_worker = JobLeaseStore.read(job_id).get("worker_id", "unknown") if JobLeaseStore.read(job_id) else "unknown"
        TelemetryLogger.log_event(
            "reclaim_winner",
            job_id=job_id,
            worker_id=WORKER_ID,
            prev_worker_id=prev_worker
        )
        
        # This worker won the reclaim
        with _exclusive_lock(JOBS_DB_LOCK_PATH):
            db = JobsDB._read_unlocked()
            job = db.get(job_id)
            
            if job and job["status"] == JobStatus.RUNNING:
                attempts = JobAttemptStore.get_attempts(job_id)
                
                if attempts < OPAL_MAX_RETRIES:
                    # Retry: Requeue with backoff
                    backoff_idx = min(attempts, len(OPAL_RETRY_BACKOFFS) - 1)
                    backoff_secs = OPAL_RETRY_BACKOFFS[backoff_idx]
                    
                    logger.warning(f"[Lease] ♻️ Reclaiming job {job_id} (Attempt {attempts}/{OPAL_MAX_RETRIES}) -> QUEUED (backoff={backoff_secs}s)")
                    
                    job["status"] = JobStatus.QUEUED
                    job["worker_id"] = None
                    job["error"] = {"message": f"lease_expired_retry_{attempts}"}
                    job["updated_at"] = datetime.now().isoformat()
                    
                    # Fix#2: Set backoff
                    JobAttemptStore.set_backoff(job_id, backoff_secs)
                    
                    # A2.1.1: Log backoff event
                    TelemetryLogger.log_event(
                        "backoff_applied",
                        job_id=job_id,
                        attempt=attempts,
                        backoff_secs=backoff_secs
                    )
                    
                    # A2.1.1: Log retry scheduled
                    TelemetryLogger.log_event(
                        "retry_scheduled",
                        job_id=job_id,
                        attempt=attempts,
                        reason="lease_expired"
                    )
                else:
                    # Max retries reached: Fail permanently
                    logger.error(f"[Lease] 🛑 Reclaiming job {job_id} (Max retries {OPAL_MAX_RETRIES} reached) -> FAILED")
                    job["status"] = JobStatus.FAILED
                    job["error"] = {"message": "max_retries_exceeded_a2"}
                    job["completed_at"] = datetime.now().isoformat()
                    job["updated_at"] = datetime.now().isoformat()
                    
                    # A2.1.1: Log max retries reached
                    TelemetryLogger.log_event(
                        "max_retries_reached",
                        job_id=job_id,
                        final_attempt=attempts
                    )
                
                _atomic_write_json(JOBS_DB_PATH, db)
            
            # Always clean up the lease file under lock
            JobLeaseStore.force_delete(job_id)

def run_job_gc():
    RETENTION_SECONDS = 24 * 3600
    now = datetime.now()
    cutoff_time = now.timestamp() - RETENTION_SECONDS
    
    all_jobs = JobsDB.get_all_jobs()
    deleted_count = 0
    
    for job_id, job in list(all_jobs.items()):
        if job["status"] not in [JobStatus.SUCCEEDED, JobStatus.FAILED]:
            continue
            
        ref_time_str = job.get("completed_at") or job.get("updated_at")
        if not ref_time_str:
            continue
            
        try:
            ref_time = datetime.fromisoformat(ref_time_str.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
            
        if ref_time < cutoff_time:
            logger.info(f"GC: Deleting expired job {job_id}")
            artifact_dir = ARTIFACTS_DIR / job_id
            if artifact_dir.exists():
                shutil.rmtree(artifact_dir)
            JobsDB.delete_job(job_id)
            deleted_count += 1
            
    if deleted_count > 0:
        logger.info(f"GC: Purged {deleted_count} jobs.")

def main():
    logger.info(f"Starting OPAL Massing Engine Worker {WORKER_ID}...")
    
    # Prep Semaphore
    slots = int(os.environ.get("OPAL_ENGINE_SLOTS", "1"))
    sem_path = PROJECT_ROOT / "runtime/locks/engine_slots"
    semaphore = EngineSemaphore(sem_path, slots)
    
    # Initial Recovery (A2: Lease reclaimer will handle stale jobs via TTL)
    # recover_crashed_jobs()
    
    logger.info(f"Polling JobsDB (Atomic Lease mode)...")
    
    # Force initial heartbeat
    _heartbeat_tick(force=True)
    
    loop_count = 0
    while True:
        try:
            _heartbeat_tick()
            loop_count += 1
            if loop_count % 100 == 0:
                 run_job_gc()
            
            if loop_count % 10 == 0:
                 reclaim_expired_leases()

            # A1: Atomic Claim
            # We no longer poll queue list -> update race. We execute explicit atomic claim.
            job = JobsDB.claim_next_job(WORKER_ID)
            
            if job:
                logger.info(f"⏩ Claimed job {job['id']}")
                
                # A2-Phase1: Create Lease
                current_attempt = JobAttemptStore.get_attempts(job["id"]) or 1
                JobLeaseStore.create(
                    job_id=job["id"],
                    worker_id=WORKER_ID,
                    host=HOSTNAME,
                    ttl_secs=OPAL_LEASE_TTL_SECS,
                    meta={"pid": os.getpid()}
                )
                
                # A2.1.1: Log telemetry event
                TelemetryLogger.log_event(
                    "lease_created",
                    job_id=job["id"],
                    worker_id=WORKER_ID,
                    ttl=OPAL_LEASE_TTL_SECS,
                    attempt=current_attempt
                )
                
                # Renew Thread logic
                stop_evt = threading.Event()
                def _renew_loop():
                    while not stop_evt.wait(OPAL_LEASE_RENEW_SECS):
                        ok = JobLeaseStore.renew(job["id"], WORKER_ID, OPAL_LEASE_TTL_SECS)
                        if not ok:
                            logger.warning(f"[Lease] Renew failed for {job['id']}")
                
                renew_thread = threading.Thread(target=_renew_loop, daemon=True)
                renew_thread.start()
                
                try:
                    outputs, provenance = run_massing_engine_adapter(job, semaphore)
                    JobsDB.update_job(job["id"], {
                        "status": JobStatus.SUCCEEDED,
                        "completed_at": datetime.now().isoformat(),
                        "outputs": outputs,
                        "run_provenance": provenance
                    })
                    logger.info(f"✅ Job {job['id']} SUCCEEDED")
                except Exception as e:
                    logger.error(f"❌ Job {job['id']} FAILED: {e}")
                    JobsDB.update_job(job["id"], {
                        "status": JobStatus.FAILED,
                        "completed_at": datetime.now().isoformat(),
                        "error": {"message": str(e)}
                    })
                finally:
                    # Stop renewal thread and release lease
                    stop_evt.set()
                    renew_thread.join(timeout=2)
                    JobLeaseStore.release(job["id"], WORKER_ID)
                    # A2.1: Success! Clear attempts
                    JobAttemptStore.clear(job["id"])
            else:
                # No jobs, sleep
                time.sleep(2)
        except KeyboardInterrupt:
            logger.info("Stopping...")
            break
        except Exception as e:
            logger.error(f"Error in loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
