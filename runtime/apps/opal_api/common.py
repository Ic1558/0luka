import json
import uuid
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, List
from pydantic import BaseModel

# ═══════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════
_DEFAULT_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = Path(
    os.environ.get("LUKA_BASE")
    or os.environ.get("OLUKA_ROOT")
    or str(_DEFAULT_ROOT)
).resolve()
TELEMETRY_PATH = PROJECT_ROOT / "observability" / "telemetry" / "health.latest.json"
BUDGET_PATH = PROJECT_ROOT / "observability" / "finance" / "budget.json"
HEALTH_LOG_PATH = PROJECT_ROOT / "observability" / "logs" / "health.log"
ARTIFACTS_DIR = PROJECT_ROOT / "runtime" / "opal_artifacts"

# --- A2 Phase 0: Worker Registry (Heartbeat) ---
WORKER_REGISTRY_PATH = PROJECT_ROOT / "runtime" / "worker_registry.json"
WORKER_REGISTRY_LOCK_PATH = str(WORKER_REGISTRY_PATH) + ".lock"
OPAL_CLOCK_SKEW_TOLERANCE_SECS = float(os.getenv('OPAL_CLOCK_SKEW_TOLERANCE_SECS', '3'))
OPAL_IDENTITY_DIR = os.getenv('OPAL_IDENTITY_DIR', 'runtime/identity')
OPAL_HOST_ID_FILE = os.getenv('OPAL_HOST_ID_FILE', 'runtime/identity/host.json')
OPAL_WORKER_SEQ_FILE = os.getenv('OPAL_WORKER_SEQ_FILE', 'runtime/identity/worker_seq.json')

OPAL_HEARTBEAT_INTERVAL_SECS = float(os.environ.get("OPAL_HEARTBEAT_INTERVAL", "2"))
OPAL_WORKER_TTL_SECS = float(os.environ.get("OPAL_WORKER_TTL", "10"))
OPAL_REGISTRY_PRUNE_EVERY_SECS = float(os.environ.get("OPAL_REGISTRY_PRUNE_EVERY_SECS", "10"))

# --- A2 Phase 1: Lease TTL Sidecars ---
JOB_LEASE_DIR = PROJECT_ROOT / "runtime" / "job_leases"
JOB_LEASE_LOCK_PATH = str(JOB_LEASE_DIR / ".lock")
OPAL_LEASE_TTL_SECS = float(os.environ.get("OPAL_LEASE_TTL", "15"))
OPAL_LEASE_RENEW_SECS = float(os.environ.get("OPAL_LEASE_RENEW", "5"))

# --- A2 Phase 2.1: Retry Policy & Idempotency ---
JOB_ATTEMPT_DIR = PROJECT_ROOT / "runtime" / "job_attempts"
JOB_ATTEMPT_LOCK_PATH = str(JOB_ATTEMPT_DIR / ".lock")
OPAL_MAX_RETRIES = int(os.environ.get("OPAL_MAX_RETRIES", "2"))
OPAL_RETRY_BACKOFFS = [int(x) for x in os.environ.get("OPAL_RETRY_BACKOFFS", "3,8,15").split(",")]

# --- A2.1.1: Observability Pack (Telemetry Events) ---
OPAL_TELEMETRY_DIR = PROJECT_ROOT / "observability" / "telemetry"
OPAL_EVENTS_LOG = OPAL_TELEMETRY_DIR / "opal_events.jsonl"
OPAL_TELEMETRY_ENABLED = os.environ.get("OPAL_TELEMETRY_ENABLED", "1") == "1"
OPAL_TELEMETRY_MAX_SIZE_MB = int(os.environ.get("OPAL_TELEMETRY_MAX_SIZE_MB", "10"))

DISPLAY_ROOT = PROJECT_ROOT
DISPLAY_ROOT_STR = str(DISPLAY_ROOT)
DISPLAY_ROOT_REF = "${ROOT}"

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
    id: str
    name: str # Human friendly name
    kind: str
    mime: str
    sha256: str
    href: str

class JobError(BaseModel):
    message: str

class JobInfo(BaseModel):
    id: str
    status: str

class RunProvenance(BaseModel):
    engine: str
    version: Optional[str] = None
    input_checksum: Optional[str] = None

class JobDetail(BaseModel):
    id: str
    status: str
    outputs: Optional[List[JobOutput]] = None
    error: Optional[JobError] = None
    run_provenance: Optional[RunProvenance] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

# ═══════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════
def read_json_file(path: Path) -> Optional[dict]:
    try:
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"[OPAL API] Error reading {path}: {e}")
    return None

def normalize_paths(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: normalize_paths(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [normalize_paths(v) for v in obj]
    if isinstance(obj, str):
        return obj.replace(DISPLAY_ROOT_STR, DISPLAY_ROOT_REF)
    return obj

# ═══════════════════════════════════════════
# A2.1.1: Telemetry Logger (Out-of-band Events)
# ═══════════════════════════════════════════
import threading

class TelemetryLogger:
    """
    A2.1.1: Thread-safe JSONL event logger for lease/attempt lifecycle.
    
    All events are written out-of-band (no ABI impact) to observability/telemetry/opal_events.jsonl
    """
    _lock = threading.Lock()
    
    @classmethod
    def _ensure_dir(cls):
        OPAL_TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def _rotate_if_needed(cls):
        """Rotate log file if it exceeds max size."""
        if not OPAL_EVENTS_LOG.exists():
            return
        
        size_mb = OPAL_EVENTS_LOG.stat().st_size / (1024 * 1024)
        if size_mb >= OPAL_TELEMETRY_MAX_SIZE_MB:
            # Rotate: opal_events.jsonl -> opal_events.YYYYMMDD_HHMMSS.jsonl
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            rotated = OPAL_TELEMETRY_DIR / f"opal_events.{ts}.jsonl"
            OPAL_EVENTS_LOG.rename(rotated)
    
    @classmethod
    def log_event(cls, event_type: str, **kwargs):
        """
        Log a telemetry event as a single JSONL line.
        
        Args:
            event_type: Event name (e.g., 'lease_created', 'attempt_started')
            **kwargs: Event-specific fields
        """
        if not OPAL_TELEMETRY_ENABLED:
            return
        
        event = {
            "ts": _now_iso_utc(),
            "event": event_type,
            **kwargs
        }
        
        with cls._lock:
            try:
                cls._ensure_dir()
                cls._rotate_if_needed()
                
                with open(OPAL_EVENTS_LOG, "a") as f:
                    f.write(json.dumps(event) + "\n")
            except Exception as e:
                # Telemetry failures should not crash the worker
                print(f"[TELEMETRY] Failed to log event {event_type}: {e}")

# ═══════════════════════════════════════════
# A1: JobsDB Atomic Locking Helper
# ═══════════════════════════════════════════
from contextlib import contextmanager
import fcntl
import tempfile
import socket
from datetime import timezone

JOBS_DB_PATH = PROJECT_ROOT / "observability" / "jobs_db.json"
JOBS_DB_LOCK_PATH = str(JOBS_DB_PATH) + ".lock"
UPLOADS_DIR = PROJECT_ROOT / "observability" / "uploads"

def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")



def _now_epoch_utc() -> float:
    """UTC epoch seconds (float)."""
    return datetime.now(timezone.utc).timestamp()
@contextmanager
def _exclusive_lock(lock_path: str):
    """Acquires an exclusive file lock using fcntl."""
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    # Using 0o600 to restrict access to the owner (security hardening)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        # Blocking exclusive lock
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

def _atomic_write_json(path: Path, data: Any):
    """Writes JSON to a temp file then atomically moves it to destination."""
    path_obj = Path(path)
    d = path_obj.parent
    d.mkdir(parents=True, exist_ok=True)
    
    with tempfile.NamedTemporaryFile("w", dir=d, delete=False, encoding='utf-8') as tf:
        json.dump(data, tf, indent=2, ensure_ascii=False)
        tf.flush()
        os.fsync(tf.fileno())
        tmp_name = tf.name
        
    os.replace(tmp_name, str(path))

# ═══════════════════════════════════════════
# Persistence (JobsDB)
# ═══════════════════════════════════════════
class JobsDB:
    @staticmethod
    def _read_unlocked() -> dict[str, Any]:
        """Reads DB directly (caller must hold lock if modifying)."""
        if not JOBS_DB_PATH.exists():
            return {}
        try:
            with open(JOBS_DB_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    
    @classmethod
    def create_job(cls, job_id: str, prompt: str, input_file: str, metadata: Optional[dict] = None) -> dict:
        with _exclusive_lock(JOBS_DB_LOCK_PATH):
            db = cls._read_unlocked()
            job = {
                "id": job_id,
                "prompt": prompt,
                "input_file": input_file,
                "metadata": metadata or {},
                "status": JobStatus.QUEUED,
                "created_at": _now_iso_utc(),
                "updated_at": _now_iso_utc(),
                "started_at": None,
                "completed_at": None,
                "outputs": [],
                "error": None,
                "worker_id": None # A1: Worker Identity
            }
            db[job_id] = job
            _atomic_write_json(JOBS_DB_PATH, db)
            return job

    @classmethod
    def get_job(cls, job_id: str) -> Optional[dict]:
        # Reads are safe without lock for pure retrieval (eventual consistency)
        # But for strict consistency, one might lock. 
        # A1 Spec: "Lock all write path". Reads can be optimistic.
        db = cls._read_unlocked()
        return db.get(job_id)

    @classmethod
    def get_all_jobs(cls) -> dict[str, Any]:
        """Returns all jobs (for GC and Recovery)."""
        return cls._read_unlocked()

    @classmethod
    def delete_job(cls, job_id: str):
        with _exclusive_lock(JOBS_DB_LOCK_PATH):
            db = cls._read_unlocked()
            if job_id in db:
                del db[job_id]
                _atomic_write_json(JOBS_DB_PATH, db)

    @classmethod
    def get_next_queued_job(cls) -> Optional[dict]:
        """Legacy access - peek only."""
        db = cls._read_unlocked()
        for job in db.values():
            if job["status"] == JobStatus.QUEUED:
                return job
        return None
        
    @classmethod
    def claim_next_job(cls, worker_id: str) -> Optional[dict]:
        """
        A2.1: Atomic Lease Acquisition with backoff awareness.
        Finds first queued job that is not in backoff, updates it, and persists - all under lock.
        """
        with _exclusive_lock(JOBS_DB_LOCK_PATH):
            db = cls._read_unlocked()
            candidate = None
            for job in db.values():
                if job["status"] == JobStatus.QUEUED:
                    # A2.1: Skip jobs in backoff period
                    if JobAttemptStore.should_delay(job["id"]):
                        continue
                    candidate = job
                    break
            
            if not candidate:
                return None
                
            # Update state
            candidate["status"] = JobStatus.RUNNING
            candidate["worker_id"] = worker_id
            candidate["started_at"] = _now_iso_utc()
            candidate["updated_at"] = _now_iso_utc()
            
            _atomic_write_json(JOBS_DB_PATH, db)
            return candidate

    @classmethod
    def update_job(cls, job_id: str, updates: dict[str, Any]) -> Optional[dict]:
        with _exclusive_lock(JOBS_DB_LOCK_PATH):
            db = cls._read_unlocked()
            if job_id not in db:
                return None
            
            job = db[job_id]
            job.update(updates)
            job["updated_at"] = _now_iso_utc()
            db[job_id] = job
            _atomic_write_json(JOBS_DB_PATH, db)
            return job

class WorkerRegistry:
    """A2-Phase0: Single-host registry that supports multi-host semantics via heartbeat entries.
    Stored outside JobsDB to avoid /api/jobs ABI drift.
    """

    @classmethod
    def _read_unlocked(cls) -> dict[str, Any]:
        if not WORKER_REGISTRY_PATH.exists():
            return {
                "version": 1,
                "updated_at": _now_iso_utc(),
                "workers": {},
            }
        try:
            with open(WORKER_REGISTRY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return {"version": 1, "updated_at": _now_iso_utc(), "workers": {}}
            
        if not isinstance(data, dict):
            return {"version": 1, "updated_at": _now_iso_utc(), "workers": {}}
        data.setdefault("version", 1)
        data.setdefault("workers", {})
        return data

    @classmethod
    def upsert_heartbeat(
        cls,
        worker_id: str,
        host: str,
        engine_slots: int,
        meta: Optional[dict[str, Any]] = None,
    ) -> None:
        """Insert/update a worker heartbeat entry."""
        meta = meta or {}
        now = _now_iso_utc()

        with _exclusive_lock(str(WORKER_REGISTRY_LOCK_PATH)):
            reg = cls._read_unlocked()
            workers = reg.get("workers", {})

            prev = workers.get(worker_id) or {}
            started_at = prev.get("started_at") or now

            workers[worker_id] = {
                "worker_id": worker_id,
                "host": host,
                "started_at": started_at,
                "last_seen": now,
                "engine_slots": int(engine_slots),
                "status": "alive",
                "meta": meta,
            }

            reg["updated_at"] = now
            reg["workers"] = workers
            _atomic_write_json(WORKER_REGISTRY_PATH, reg)

    @classmethod
    def prune_stale(cls, ttl_secs: Optional[float] = None) -> int:
        """Remove stale workers whose last_seen is older than TTL.
        Returns number of pruned workers.
        """
        ttl = float(ttl_secs) if ttl_secs is not None else float(OPAL_WORKER_TTL_SECS)
        now = datetime.now(timezone.utc)

        def parse_ts(s: str) -> Optional[datetime]:
            if not isinstance(s, str):
                return None
            try:
                # _now_iso_utc() emits Z suffix
                if s.endswith("Z"):
                    s = s[:-1] + "+00:00"
                return datetime.fromisoformat(s)
            except Exception:
                return None

        with _exclusive_lock(str(WORKER_REGISTRY_LOCK_PATH)):
            reg = cls._read_unlocked()
            workers = reg.get("workers", {})
            if not isinstance(workers, dict):
                workers = {}
            
            # Global Prune Throttling (A3.1)
            last_pruned_str = reg.get("last_pruned_at")
            if last_pruned_str:
                last_pruned = parse_ts(last_pruned_str)
                if last_pruned and (now - last_pruned).total_seconds() < OPAL_REGISTRY_PRUNE_EVERY_SECS:
                    return 0

            to_delete = []
            for wid, w in workers.items():
                last_seen = parse_ts((w or {}).get("last_seen"))
                if last_seen is None:
                    continue
                age = (now - last_seen).total_seconds()
                if age > ttl:
                    to_delete.append(wid)

            if not to_delete:
                # Update timestamp to avoid frequent rescans (A3.1)
                reg["last_pruned_at"] = _now_iso_utc()
                _atomic_write_json(WORKER_REGISTRY_PATH, reg)
                return 0

            for wid in to_delete:
                workers.pop(wid, None)

            reg["updated_at"] = _now_iso_utc()
            reg["last_pruned_at"] = _now_iso_utc()
            reg["workers"] = workers
            _atomic_write_json(WORKER_REGISTRY_PATH, reg)

            return len(to_delete)

    @classmethod
    def list_workers(cls) -> list[dict[str, Any]]:
        """Read-only list of workers."""
        with _exclusive_lock(str(WORKER_REGISTRY_LOCK_PATH)):
            reg = cls._read_unlocked()
            return list(reg.get("workers", {}).values())



class IdentityManager:
    """Federation-ready identity.

    Produces a stable `host_id` (UUID) persisted on disk, and a per-process `worker_seq`
    allocated atomically (file-locked) so worker IDs remain unique across restarts.

    Worker ID format (stable across PID changes):
      <host_id>:<worker_seq>
    """

    _cached_host_id: Optional[str] = None

    @classmethod
    def _ensure_identity_dir(cls) -> Path:
        d = Path(OPAL_IDENTITY_DIR)
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def get_host_id(cls) -> str:
        if cls._cached_host_id:
            return cls._cached_host_id

        cls._ensure_identity_dir()
        host_path = Path(OPAL_HOST_ID_FILE)

        if host_path.exists():
            try:
                data = json.loads(host_path.read_text(encoding="utf-8"))
                host_id = str(data.get("host_id") or "").strip()
                if host_id:
                    cls._cached_host_id = host_id
                    return host_id
            except Exception:
                pass

        host_id = str(uuid.uuid4())
        payload = {"host_id": host_id, "created_at": _now_iso_utc()}
        _atomic_write_json(host_path, payload)
        cls._cached_host_id = host_id
        return host_id

    @classmethod
    def allocate_worker_seq(cls) -> int:
        cls._ensure_identity_dir()
        seq_path = Path(OPAL_WORKER_SEQ_FILE)
        lock_path = str(seq_path) + ".lock"

        with _exclusive_lock(lock_path):
            current = 0
            if seq_path.exists():
                try:
                    data = json.loads(seq_path.read_text(encoding="utf-8"))
                    current = int(data.get("next_seq", 0))
                except Exception:
                    current = 0

            worker_seq = current
            payload = {"next_seq": worker_seq + 1, "updated_at": _now_iso_utc()}
            _atomic_write_json(seq_path, payload)
            return worker_seq

    @classmethod
    def make_worker_id(cls) -> str:
        host_id = cls.get_host_id()
        worker_seq = cls.allocate_worker_seq()
        return f"{host_id}:{worker_seq}"

class JobLeaseStore:
    """A2-Phase1: Lease TTL sidecar persistence.
    Stored outside JobsDB response to ensure zero ABI drift.
    """

    @classmethod
    def _get_path(cls, job_id: str) -> Path:
        return JOB_LEASE_DIR / f"{job_id}.json"

    @classmethod
    def create(cls, job_id: str, worker_id: str, host: str, ttl_secs: float, attempt: int = 1, meta: Optional[dict[str, Any]] = None) -> dict:
        meta = meta or {}
        now = _now_iso_utc()
        expires_at = (datetime.now(timezone.utc).timestamp() + ttl_secs)
        expires_at_iso = datetime.fromtimestamp(expires_at, timezone.utc).isoformat().replace("+00:00", "Z")
        
        lease = {
            "job_id": job_id,
            "worker_id": worker_id,
            "host": host,
            "attempt": attempt,
            "granted_at": now,
            "expires_at": expires_at_iso,
            "last_renewed_at": now,
            "meta": meta
        }
        
        with _exclusive_lock(JOB_LEASE_LOCK_PATH):
            _atomic_write_json(cls._get_path(job_id), lease)
            return lease

    @classmethod
    def renew(cls, job_id: str, worker_id: str, ttl_secs: float) -> bool:
        path = cls._get_path(job_id)
        if not path.exists():
            return False
            
        with _exclusive_lock(JOB_LEASE_LOCK_PATH):
            try:
                with open(path, "r") as f:
                    lease = json.load(f)
            except Exception:
                return False
                
            if lease.get("worker_id") != worker_id:
                return False
                
            now = _now_iso_utc()
            expires_at = (datetime.now(timezone.utc).timestamp() + ttl_secs)
            expires_at_iso = datetime.fromtimestamp(expires_at, timezone.utc).isoformat().replace("+00:00", "Z")
            
            lease["expires_at"] = expires_at_iso
            lease["last_renewed_at"] = now
            _atomic_write_json(path, lease)
            return True

    @classmethod
    def release(cls, job_id: str, worker_id: str) -> None:
        path = cls._get_path(job_id)
        if not path.exists():
            return
            
        with _exclusive_lock(JOB_LEASE_LOCK_PATH):
            try:
                with open(path, "r") as f:
                    lease = json.load(f)
                if lease.get("worker_id") == worker_id:
                    path.unlink(missing_ok=True)
            except Exception:
                pass

    @classmethod
    def read(cls, job_id: str) -> Optional[dict]:
        path = cls._get_path(job_id)
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    @classmethod
    def list_expired(cls) -> list[str]:
        """Scan directory for leases that have passed their expires_at + skew tolerance."""
        if not JOB_LEASE_DIR.exists():
            return []
            
        now = _now_epoch_utc()
        expired_ids = []
        
        with _exclusive_lock(JOB_LEASE_LOCK_PATH):
            for p in JOB_LEASE_DIR.glob("*.json"):
                if p.name == ".lock": continue
                try:
                    with open(p, "r") as f:
                        lease = json.load(f)
                    
                    exp_str = lease.get("expires_at", "")
                    if not exp_str:
                        continue
                        
                    # Parse timestamp with fallback
                    try:
                        exp_ts = _parse_iso_to_epoch(exp_str)
                    except (ValueError, NameError):
                        if exp_str.endswith("Z"):
                            exp_str = exp_str[:-1] + "+00:00"
                        exp_ts = datetime.fromisoformat(exp_str).timestamp()

                    # Clock Skew Guard
                    if now > (exp_ts + OPAL_CLOCK_SKEW_TOLERANCE_SECS):
                        expired_ids.append(lease["job_id"])
                except Exception:
                    continue
        return expired_ids

    @classmethod
    def force_delete(cls, job_id: str):
        path = cls._get_path(job_id)
        with _exclusive_lock(JOB_LEASE_LOCK_PATH):
            path.unlink(missing_ok=True)

class JobAttemptStore:
    """A2-Phase2.1: Out-of-band attempt tracking to avoid JobsDB ABI drift."""

    @classmethod
    def _get_path(cls, job_id: str) -> Path:
        return JOB_ATTEMPT_DIR / f"{job_id}.json"

    @classmethod
    def get_attempts(cls, job_id: str) -> int:
        path = cls._get_path(job_id)
        if not path.exists():
            return 0
        try:
            with open(path, "r") as f:
                data = json.load(f)
                return int(data.get("attempts", 0))
        except Exception:
            return 0

    @classmethod
    def increment_attempt(cls, job_id: str) -> int:
        path = cls._get_path(job_id)
        with _exclusive_lock(JOB_ATTEMPT_LOCK_PATH):
            attempts = 0
            if path.exists():
                try:
                    with open(path, "r") as f:
                        data = json.load(f)
                        attempts = int(data.get("attempts", 0))
                except Exception:
                    pass
            
            attempts += 1
            _atomic_write_json(path, {
                "job_id": job_id,
                "attempts": attempts,
                "updated_at": _now_iso_utc()
            })
            return attempts

    @classmethod
    def try_mark_reclaimed(cls, job_id: str, worker_id: str, reason: str) -> bool:
        """Atomic winner selection. Returns True if this worker won the reclaim."""
        path = cls._get_path(job_id)
        with _exclusive_lock(JOB_ATTEMPT_LOCK_PATH):
            data = {"job_id": job_id, "attempts": 0}
            if path.exists():
                try:
                    with open(path, "r") as f:
                        data = json.load(f)
                except Exception:
                    pass
            
            # Check if already reclaimed
            if data.get("reclaim", {}).get("reclaimed_by"):
                return False
            
            # Mark as reclaimed by this worker
            data["reclaim"] = {
                "reclaimed_by": worker_id,
                "reclaimed_at": _now_iso_utc(),
                "reason": reason
            }
            _atomic_write_json(path, data)
            return True

    @classmethod
    def set_backoff(cls, job_id: str, backoff_secs: int):
        """Set not_before timestamp for backoff."""
        path = cls._get_path(job_id)
        with _exclusive_lock(JOB_ATTEMPT_LOCK_PATH):
            data = {"job_id": job_id, "attempts": 0}
            if path.exists():
                try:
                    with open(path, "r") as f:
                        data = json.load(f)
                except Exception:
                    pass
            
            not_before_ts = datetime.now(timezone.utc).timestamp() + backoff_secs
            data["not_before"] = datetime.fromtimestamp(not_before_ts, timezone.utc).isoformat().replace("+00:00", "Z")
            data["backoff_secs_applied"] = backoff_secs
            _atomic_write_json(path, data)

    @classmethod
    def should_delay(cls, job_id: str) -> bool:
        """Check if job should be delayed due to backoff."""
        path = cls._get_path(job_id)
        if not path.exists():
            return False
        try:
            with open(path, "r") as f:
                data = json.load(f)
                not_before_str = data.get("not_before")
                if not not_before_str:
                    return False
                not_before = datetime.fromisoformat(not_before_str.replace("Z", "+00:00"))
                return datetime.now(timezone.utc) < not_before
        except Exception:
            return False

    @classmethod
    def clear(cls, job_id: str):
        path = cls._get_path(job_id)
        with _exclusive_lock(JOB_ATTEMPT_LOCK_PATH):
            path.unlink(missing_ok=True)


def _parse_iso_to_epoch(iso_str: str) -> float:
    return datetime.fromisoformat(iso_str.replace('Z', '+00:00')).timestamp()
