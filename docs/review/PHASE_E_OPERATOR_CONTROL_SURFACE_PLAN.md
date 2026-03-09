# Phase E Operator Control Surface Plan

## Motivation
Operators require a unified and stable read-model to monitor the 0luka runtime without directly inspecting raw logs or state files. Currently, operator-relevant data is fragmented across various endpoints and internal helpers. Phase E formalizes this into a stable, documented read surface.

## New Endpoints

### 1. GET /api/operator/approval_state
**Description:** Returns the current effective approval status for all remediation lanes (memory, worker, api, etc.).
**Response Schema:**
```json
{
  "lanes": {
    "lane_id": {
      "status": "allowed|approval_required|denied|unavailable",
      "reason": "string",
      "approved": "boolean",
      "expires_at": "ISO-8601|null",
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
**Description:** Provides visibility into the current pending and recently processed remediation items.
**Response Schema:**
```json
{
  "items": [
    {
      "id": "string",
      "lane": "string",
      "action": "string",
      "state": "queued|processing|completed|failed",
      "attempts": "integer",
      "created_at": "ISO-8601"
    }
  ]
}
```

### 3. GET /api/operator/runtime_decisions
**Description:** Retrieves a chronological log of recent high-level runtime decisions (remediation triggers, escalation shifts).
**Response Schema:**
```json
{
  "entries": [
    {
      "timestamp": "ISO-8601",
      "lane": "string",
      "action": "string",
      "decision": "string",
      "result": "string"
    }
  ]
}
```

### 4. GET /api/operator/policy_drift
**Description:** Reports any drift between the intended autonomy policy and the current runtime configuration.
**Response Schema:**
```json
{
  "checks": {
    "approval_log_consistency": "OK|STALE|DRIFT",
    "expiry_consistency": "OK|ERROR",
    "env_gate_consistency": "OK|MISMATCH"
  }
}
```

### 5. GET /api/operator/qs_overview
**Description:** Provides an aggregated summary of active and historical QS job runs.
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

## Read Model Sources
Data is derived strictly from existing authoritative files:
- `runtime_root/state/approval_state.json`
- `runtime_root/state/remediation_queue.jsonl`
- `runtime_root/state/remediation_history.jsonl`
- `runtime_root/state/qs_runs/*.json`

## Isolation Guarantees
- **Strictly Read-Only:** Implementation will use read-only file handles and no state mutation logic.
- **No Dispatcher Coupling:** These endpoints query state asynchronously; they do not interact with the dispatcher loop or task ingestion.
- **Policy Neutral:** Observation of the policy does not trigger re-evaluation or modification of the policy.

## Test Plan
**New Test File:** `core/verify/test_operator_control_surface.py`
- `test_operator_endpoints_return_json`: Verify all new routes return 200 and valid JSON.
- `test_operator_endpoints_are_read_only`: Verify non-GET methods are blocked.
- `test_operator_endpoints_degrade_gracefully`: Verify behavior when state files are missing.
- `test_no_runtime_drift_during_operator_queries`: Verify that system state hashes remain unchanged after multiple API calls.

## Non-Claims
- Phase E is **not** an execution plane (cannot approve or enqueue via these endpoints).
- Phase E does **not** introduce new authoritative state (all data is projected from existing sources).
- Phase E does **not** provide real-time log streaming (polling-based read model).
