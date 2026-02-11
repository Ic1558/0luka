# OPAL Track A3 — Control Plane (Federation Protocol)

**Status:** STARTED
**Dependencies:** A2.2 (stable identity)

---

## 1. Mission
Build the **Control Plane** visibility into the federation.
Currently, OPAL is a set of autonomous workers. A3 adds the "Brain" API to visualize and oversee the fleet.
**Constraint:** Read-only APIs for now. No scheduling changes.

## 2. Specs

### 3.0 Node/Worker Inventory API
New endpoints in `opal_api_server.py`:

#### `GET /api/nodes`
- **Goal:** View fleet health at Host level.
- **Logic:** Group `WorkerRegistry` entries by `host_id`.
- **Response schema:**
  ```json
  {
    "nodes": [
      {
        "host_id": "550e...",
        "hostname": "mac-mini.local",
        "status": "healthy",
        "worker_count": 5,
        "last_seen_max": "2026-...",
        "engine_slots_total": 5
      }
    ]
  }
  ```

#### `GET /api/workers`
- **Goal:** Raw view of registry.
- **Logic:** Dump `WorkerRegistry.list_workers()`.
- **Query Params:** `?status=alive` (filter by TTL check).

### 3.1 Registry Hygiene
- **Issue:** `prune_stale()` currently runs on *every* heartbeat tick of *every* worker. This creates lock contention on `worker_registry.json`.
- **Fix:** Start a dedicated `RegistryCleaner` thread in `opal_api_server.py` OR stick to Worker-based but rate-limit it (e.g. `if loop % 100 == 0`).
- **Policy:** `OPAL_REGISTRY_PRUNE_EVERY_SECS` (default 60s).

## 3. DoD (Definition of Done)
1. **API Reachability:** `curl /api/nodes` returns JSON list.
2. **Aggregation:** 5 workers on 1 host -> 1 Node entry, `worker_count=5`.
3. **Hygiene:** Old workers disappear from API after TTL, without manual file deletion.

## 4. Implementation Plan
1. **Refactor Hygiene:** Move `prune_stale` invocation or rate-limit it.
2. **Common Helpers:** Add `group_by_host` logic in `WorkerRegistry`? Or keep logic in API.
3. **API Endpoints:** Add routes to `opal_api_server.py`.
4. **Verify:** New script `tests/opal_a3_verify.zsh`.
