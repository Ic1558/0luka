# Phase E Operator Read Surface Contract

## Scope
Operator read-model for high-level runtime observability. This document defines the stable JSON contract for operator dashboards and monitoring tools within Mission Control.

## Endpoints

### 1. GET /api/operator/approval_state
**Description:** Provides the current effective approval status for all remediation lanes.
**Response Schema:**
```json
{
  "lanes": {
    "lane_id": {
      "status": "string (allowed|approval_required|denied|unavailable)",
      "reason": "string",
      "approved": "boolean",
      "expires_at": "string|null (ISO-8601)",
      "env_gate_present": "boolean"
    }
  },
  "approval_state": {
    "exists": "boolean",
    "valid": "boolean"
  }
}
```

### 2. GET /api/operator/remediation_queue
**Description:** Retrieves the current list of pending and processed remediation items.
**Response Schema:**
```json
{
  "items": [
    {
      "id": "string",
      "lane": "string",
      "action": "string",
      "state": "string (queued|processing|completed|failed)",
      "attempts": "integer",
      "created_at": "string (ISO-8601)"
    }
  ]
}
```

### 3. GET /api/operator/runtime_decisions
**Description:** Extracts high-level runtime decisions (remediations, escalations) from logs.
**Response Schema:**
```json
{
  "entries": [
    {
      "timestamp": "string (ISO-8601)",
      "lane": "string|null",
      "action": "string|null",
      "decision": "string|null",
      "result": "string|null"
    }
  ]
}
```

### 4. GET /api/operator/policy_drift
**Description:** Reports on the consistency between defined policy and runtime state.
**Response Schema:**
```json
{
  "checks": {
    "approval_log_consistency": "string (OK|STALE|DRIFT)",
    "expiry_consistency": "string (OK|ERROR)",
    "env_gate_consistency": "string (OK|MISMATCH)"
  }
}
```

### 5. GET /api/operator/qs_overview
**Description:** Summarizes Quantity Surveying engine runs across the platform.
**Response Schema:**
```json
{
  "summary": {
    "total_runs": "integer",
    "blocked_runs": "integer",
    "pending_approval_runs": "integer"
  },
  "recent_items": [
    {
      "run_id": "string",
      "job_type": "string",
      "qs_status": "string",
      "execution_status": "string"
    }
  ]
}
```

## Determinism Guarantees
- **Ordering**: Runtime decisions are returned in reverse-chronological order (newest first). QS overview `recent_items` returns the first 20 items found in the project state directory (alphabetical/stable file sort).
- **Limits**: `runtime_decisions` is capped at 50 entries. `qs_overview` is capped at 20 `recent_items`.
- **Field Stability**: All JSON keys and status enums defined above are frozen.

## Read-Only Guarantees
- **No Mutation Paths**: Implementation audit confirms all endpoints use read-only file handles and helper functions.
- **Isolation**: These endpoints perform passive observation and do not trigger dispatcher loops or state writes.

## Compatibility Guarantees
Phase E implementation preserves the Phase D contract:
- `/api/kernel/status`, `/api/kernel/verification_history`, and `/api/kernel/guardian_history` remain functional and unchanged.
- Common truth sources (activity logs, `load_runtime_status`) are shared via read-only loaders.

## Safe Degradation
- Missing state files (e.g., `remediation_queue.jsonl`) result in empty lists (`[]`) and 200 OK responses.
- Loader exceptions are caught and return empty default objects.

## Non-Claims
- Not an execution interface (cannot initiate approvals or remediations).
- Not a real-time streaming surface (requires polling).
- Not a historical archive (recent data only).
