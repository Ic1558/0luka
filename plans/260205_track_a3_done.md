# OPAL Track A3 — Control Plane & Hygiene (DONE)

**Status:** COMPLETE  
**Date:** 2026-02-05

## 1. Components Delivered

### 1.1 Node Inventory API (A3.0)
- `GET /api/nodes`: Aggregated view by Host ID.
  - Returns: `[{host_id, worker_count, engine_slots_total, last_seen_latest}]`.
- `GET /api/workers`: Full registry dump.

### 1.2 Registry Hygiene (A3.1)
- **Global Rate Limiting:** `WorkerRegistry.prune_stale` now respects `OPAL_REGISTRY_PRUNE_EVERY_SECS` (default 10s).
- **Consensus:** Uses `last_pruned_at` in registry file to coordinate multiple workers.
- **Outcome:** Reduces lock contention while keeping registry clean of stale entries.

## 2. Verification Evidence (`tests/opal_a3_verify.zsh`)

### Control Plane
```json
// GET /api/nodes
{
  "nodes": [
    {
      "host_id": "f7fdeb45...",
      "hostname": "mac-mini.local",
      "worker_count": 3,
      "status": "healthy"
    }
  ]
}
```

### Hygiene
- Started 3 workers -> Killed -> Wait TTL -> Start 1 worker.
- Result: 3 old workers pruned. Only 1 new worker remains.
- **Pass:** `✅ Hygiene Verified: Stale workers pruned. Count=1`

## 3. Configuration
- `OPAL_REGISTRY_PRUNE_EVERY_SECS=10` (Default).
- `OPAL_WORKER_TTL=10` (Default).

## 4. Next Steps
- **A3.2 Remote Federation:** Add authentication/token logic for remote workers joining.
