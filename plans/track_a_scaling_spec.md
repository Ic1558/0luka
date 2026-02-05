# Track A: Scalability & Federation (Spec v1.0)
> **Mission**: Enable OPAL Kernel variables (Worker/Host) to scale `N > 1` without altering Kernel ABI, Semantics, or Constitution.

## Phase A1: Single-Host Multi-Worker
**Goal**: Run multiple `worker.py` instances on the same machine to maximize resource utilization, utilizing robust locking for safety.

### 1. Requirements (The "Must Haves")
- **Atomic Job Acquisition**: Prevent race conditions where two workers grab the same job.
- **Worker Identity**: Each worker process must have a persistent, unique identity (e.g., `host-pid`).
- **Isolation**: Workers must not trample on each other's temporary files or studio locks.
- **Zero Kernel Drift**: 
  - No change to `opal_api.openapi.json`.
  - No change to `JobRecord` schema (except internal metadata fields if strictly necessary, but prefer sidecars).

### 2. Implementation Specs

#### A. The "Lease" Mechanism (JobsDB)
*Current State*: `JobsDB` reads/writes JSON. Race conditions exist if multiple writers.
*Change*: Implement `fcntl` (file locking) specifically for the `claim_job` transaction.

```python
# Pseudo-code for Atomic Claim
def claim_next_job(worker_id):
    with db_lock():  # Exclusive file lock on jobs_db.json.lock
        job = find_first(status="queued")
        if job:
            job.status = "running"
            job.worker_id = worker_id  # Provenance
            job.started_at = now()
            save_db()
            return job
    return None
```

#### B. Worker Pool Management
*Architecture*:
- No complex orchestrator.
- Use `supervisord` or a simple `launch_pool.sh` script to spawn N workers.
- Each worker runs its own isolated loop.

#### C. Resource Isolation
*Problem*: `modules/studio/.opal_lock` is currently a *global* lock for the singleton implementation.
*Change*: 
- Move to **Job-Level Locking** or **Slot-Level Locking**.
- If `nano_banana_engine` supports concurrency (it runs in isolation), we remove the global `.opal_lock` and rely on unique `input_{job_id}.json` and `outputs/` partitioning.
- **Constraint**: If the underlying Engine (Studio) *cannot* run concurrently (e.g., GPU VRAM limit or single working directory), we must keep the lock but implementing a **Semaphore** (size = N).
- *Decision*: For A1, assume Engine is stateless/isolated enough OR implement a Semaphore if VRAM is the bottleneck.
- *Default*: Implement `Semaphore(N)` logic for the engine to be safe.

#### D. Crash Recovery (Reclaim)
*Logic*:
- If a worker dies while `status=running`, the job hangs forever.
- **Reclaim Strategy**:
  - Workers update a `heartbeat` timestamp in a registry (e.g., `runtime/worker_registry.json`) or directly in the job record?
  - Scope A2 says "Heartbeat registry", so for A1 we use a simpler **PID check** (since single host) or a **Timeout**.
  - *A1 Approach*: "Startup Scan". When the pool starts, any `running` job belonging to a dead PID (check via `ps`) is reset to `queued` (retry) or `failed` (dead).

### 3. Acceptance Criteria (Definition of Done)
- [x] **Concurrency Test**: Launch 5 workers. Submit 50 jobs. Ensure exactly 50 succeed (no duplicates, no dropped jobs).
- [x] **Lock Contention**: Hammer the `POST /jobs` and Worker loops. Ensure `jobs_db.json` never corrupts.
- [x] **Isolation**: Run 2 jobs simultaneously. Ensure Job A's output doesn't leak into Job B's artifacts.
- [x] **Recovery**: Kill a worker mid-job. Restart pool. Ensure job is marked failed or retried (per policy).
- [x] **No ABI Change**: `curl GET /jobs` response remains identical to v1.3.0.

---
**Phase A1 Completion Status**: COMPLETED ✅
**Evidence & Handover**: [plans/track_a1_done.md](./track_a1_done.md)
---

## Risk Matrix
| Risk | Probability | Severity | Mitigation |
| :--- | :--- | :--- | :--- |
| **DB Corruption** | Medium | High | Strict `fcntl` wrapping on all DB writes. Switch to SQLite if JSON IO allows partial writes (atomic rename is safer). |
| **Race Condition** | High | Medium | The "Claim" transaction must be atomic. |
| **OOM (Memory)** | Medium | High | Limit `MAX_RUNNING_JOBS` per worker (capacity=1) and Total Workers <= Host Capacity. |

## Phase A2: Multi-host Federation
**Goal**: Transition from Local PID-checks to a Global Heartbeat + Lease system to support Workers on multiple machines.

### 1. Requirements (The "Must Haves")
- **Worker Registry**: A shared file (registry) documenting all active workers and their status.
- **Heartbeat Mechanism**: Workers must pulse the registry periodically (e.g., every 5s).
- **Lease TTL**: Jobs are not "owned" forever; they are leased for a duration (e.g., 60s), renewable by active workers.
- **Sidecar Persistence**: Lease data must be stored such that it **does not contaminate** the public `/api/jobs` ABI.

### 2. Implementation Specs (Phased)

#### A2-Phase 0: Worker Registry (Metadata Only)
- **Path**: `runtime/worker_registry.json` (Atomic JSON).
- **Worker Logic**: On startup and every `OPAL_HEARTBEAT_INTERVAL`, update its entry:
  ```json
  {
    "worker_id": "host-pid",
    "last_seen": "ISO-TIMESTAMP",
    "host": "hostname",
    "pid": 1234,
    "engine_slots": 1
  }
  ```
- **Cleanup**: Ephemeral entries (deleted on graceful shutdown).

#### A2-Phase 1: Lease TTL sidecar
- **Path**: `runtime/job_leases/{job_id}.json`.
- **Logic**:
  - `claim_job` creates the lease file with `expires_at = now + 60s`.
  - While running, the worker updates the lease file every 20s.
  - **Reclaim Logic**: If `now > expires_at` AND (worker not in registry OR heartbeat > 2x interval) -> Reclaim job (FAILED or QUEUED with attempt++).

### 3. Acceptance Criteria (DoD)
- [ ] **Registry Accuracy**: Workers appear in `worker_registry.json` on start and disappear on exit.
- [ ] **Multi-host Simulation**: Mock registry updates from "Machine B" and ensure local reclaim handles them via Heartbeat alone.
- [ ] **Zero ABI Change**: Verify `/api/jobs` response remains identical to v1.3.0 (no lease fields visible).
- [ ] **Lock Invariants**: Ensure Registry and Lease locks do not conflict with JobsDB lock.

---

## Updated Risk Matrix
| Risk | Probability | Severity | Mitigation |
| :--- | :--- | :--- | :--- |
| **Lease Collision** | Low | High | Use `job_id` as the primary key for lease sidecars to ensure 1:1 mapping. |
| **Stale Registry** | High | Low | Implement aggressive TTL purging (Reclaim logic ignores registries older than 5 mins). |
| **IO Bottleneck** | Medium | Medium | Limit heartbeat frequency to 5-10s. |

---
**Next Steps**:
1. Implement `WorkerRegistry` class in `common.py`.
2. Implement Heartbeat thread in `worker.py`.
3. Create A2-Phase 0 verification script (`tests/opal_a2_p0_verify.zsh`).
