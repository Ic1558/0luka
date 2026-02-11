# OPAL Track A2.2 — Federation-ready Identity + Clock Guard

**Status:** DRAFT  
**Dependencies:** A2.1, A2.1.1 (Fixes applied)

---

## 1. Mission
Prepare the A2 scheduler for **Multi-Host / Multi-Cluster** federation.
This requires moving away from local PIDs to stable, universally unique identities and enforcing time correctness across distributed nodes.

## 2. Core Specs

### 2.1 Stable Worker Identity
- **Format:** `host_uuid:worker_seq` (e.g., `550e8400-e29b...:1`)
- **Persistence:** Workers must persist their identity to `runtime/identities/` to survive process restarts.
- **Goal:** If a worker process restarts on the same host, it resumes its identity (and thus its heartbeats) rather than appearing as a new node.

### 2.2 Clock Guard (Time Skew Tolerance)
- **UTC Enforcement:** All timestamps must utilize `datetime.now(timezone.utc)`.
- **Skew Tolerance:**
  - **Lease Validation:** `expires_at > now - SKEW_TOLERANCE`
  - **Registry TTL:** `last_seen > now - (TTL + SKEW_TOLERANCE)`
- **Guard:** Workers must warn/refuse to start if local clock drifts significantly from a reference (e.g., API server response header) -- *Optional for this phase, but primitives must be there.*

### 2.3 Registry Keying
- **Primary Key:** `worker_id` (process-level unique) -> Mapped to `host_id` (node-level unique).
- **Heartbeats:** Must include `host_id` to allow per-host aggregation.

## 3. Policy Defaults

| Parameter | Default | Description |
|-----------|---------|-------------|
| `OPAL_IDENTITY_ROOT` | `runtime/identities` | Persistence storage |
| `OPAL_CLOCK_SKEW_TOLERANCE_SECS` | `3` | Max allowed clock drift |
| `OPAL_ENABLE_A1_PID_RECOVERY` | `0` | **Hard disabled** |
| `OPAL_LEASE_TTL_SECS` | `15` | Keep aggressive |
| `OPAL_RECLAIM_SCAN_EVERY_LOOPS` | `10` | ~20s cycle |

## 4. DoD (Definition of Done)

### ✅ Test #1: Identity Persistence
1. Start worker pool.
2. Verify worker IDs in registry output loop.
3. Restart pool (SIGTERM -> Start).
4. Verify worker IDs remain **identical** (not new UUIDs per launch).

### ✅ Test #2: Clock Skew Simulation
1. Mock `_now_iso_utc` to return `real_time - 5s`.
2. Verify worker detects warnings or adjusts logic (Lease renewal should still succeed if within tolerance buffer).

### ✅ Test #3: A1 Recovery Disabled
1. Set `OPAL_ENABLE_A1_PID_RECOVERY=0`.
2. `grep` logs to ensure "Running A1 crash recovery scan" is ABSENT.

---

## 5. Verification Plan
Create `tests/opal_a2_2_verify.zsh`:
- Uses `dq` (directory queue) or file-based IPC to check identity persistence.
- Deterministic wait times (poll-based, not hard sleep).
