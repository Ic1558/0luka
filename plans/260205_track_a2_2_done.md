# OPAL Track A2.2 — Federation-Ready Identity + Clock Guard (DONE)

**Status:** COMPLETE  
**Date:** 2026-02-05

## 1. Components Delivered

### 1.1 Stable Identity (`IdentityManager`)
- **Host Persistence:** `runtime/identity/host.json` stores the Node UUID (`host_id`).
- **Worker Sequence:** `runtime/identity/worker_seq.json` provides atomic, monotonic sequence numbers for workers on the same host.
- **Worker ID Format:** `host_id:seq` (e.g., `550e8400...:1`).
- **Outcome:** Workers can restart and maintain "Host Identity" grouping, key for federation and scheduling affinity.

### 1.2 Clock Guard
- **Mechanism:** All critical timestamp comparisons (Lease Expiry, Heartbeat) now use `datetime.now(timezone.utc)`.
- **Tolerance:** `OPAL_CLOCK_SKEW_TOLERANCE_SECS` (default 3s) is added to valid windows.
  - `now > expires_at + 3s` -> Only reclaim if *definitely* expired.
- **Outcome:** Prevents "flickering" reclaims due to minor clock drift between nodes.

### 1.3 Fixes
- **Import Fix:** `worker.py` import logic corrected for absolute paths.
- **Verification:** `tests/opal_a2_2_verify.zsh` proves identity persistence across pool restarts.

## 2. Verification Evidence

### Identity Stability
```
[A2.2] Active workers after restart:
['b03b49db...:3', 'b03b49db...:4', 'b03b49db...:5']
[A2.2] Host ID: b03b49db...
[A2.2] ✅ Worker IDs use persistent Host ID
[A2.2] ✅ PASS: Identity stability verified
```

### Filesystem
```
runtime/identity/
├── host.json         # Stable Host UUID
├── worker_seq.json   # Monotonic global counter
└── worker_seq.json.lock
```

## 3. Next Steps (A2.2.1 / A3)
- **A3: Federation Protocol:** Now that workers have stable `host_id`, we can implement the "Control Plane" aggregation using `host_id` as the primary node key.
- **Node Agent:** Evaluate if `worker.py` should remain independent processes or be supervised by a `node_agent.py` that owns the `host_id` and heartbeats for all. (Current architecture: Workers heartbeat individually).
