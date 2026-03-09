# Mission Control Operator Dashboard Model

## Control Plane Sources
The dashboard consumes data from the following frozen endpoints:
- `GET /api/kernel/status`
- `GET /api/kernel/verification_history`
- `GET /api/kernel/guardian_history`
- `GET /api/operator/approval_state`
- `GET /api/operator/remediation_queue`
- `GET /api/operator/runtime_decisions`
- `GET /api/operator/policy_drift`
- `GET /api/operator/qs_overview`

## Dashboard Panels

### 1. Kernel Status Panel
- **Purpose:** Critical system health overview.
- **Source:** `/api/kernel/status`
- **Key Indicators:** Suite status (ok/warning), Epoch manifest presence, Environment validity.

### 2. Runtime Verification Panel
- **Purpose:** Monitor the automated verification chain.
- **Source:** `/api/kernel/verification_history`
- **Display:** List of recent task verdicts (verified/failed) with trace IDs.

### 3. Guardian Recovery Panel
- **Purpose:** Visibility into autonomous interventions.
- **Source:** `/api/kernel/guardian_history`
- **Display:** Action types (allow/freeze), reasons, and associated run IDs.

### 4. Remediation Queue Panel
- **Purpose:** Track pending system maintenance actions.
- **Source:** `/api/operator/remediation_queue`
- **Display:** Items categorized by state (queued, processing, completed, failed).

### 5. Approval State Panel
- **Purpose:** Human-in-the-loop oversight for restricted lanes.
- **Source:** `/api/operator/approval_state`
- **Display:** Status per lane, expiration timestamps, and explicit "approval required" reasons.

### 6. Policy Drift Panel
- **Purpose:** Detect configuration inconsistencies.
- **Source:** `/api/operator/policy_drift`
- **Display:** Consistency flags for logs, expiry, and environment gates.

### 7. QS Activity Panel
- **Purpose:** Business-logic specific monitoring (Quantity Surveying).
- **Source:** `/api/operator/qs_overview`
- **Display:** Aggregate counts (total, blocked, pending) and recent project status list.

## UI Data Model (Unified Schema)
```json
{
  "kernel": {
    "status": "ok|warning",
    "health": { "env_present": true, "suite_status": "ok" },
    "artifacts": { "epoch_manifest_present": true, "rotation_registry_present": true }
  },
  "verification": [
    { "trace_id": "...", "verdict": "verified", "ts": "..." }
  ],
  "guardian": [
    { "ts": "...", "action": "...", "reason": "...", "run_id": "..." }
  ],
  "remediation_queue": [
    { "id": "...", "lane": "...", "action": "...", "state": "..." }
  ],
  "approval_state": {
    "lanes": { "memory_recovery": { "status": "allowed", "approved": true } }
  },
  "policy_drift": {
    "checks": { "env_gate_consistency": "OK" }
  },
  "qs_overview": {
    "summary": { "total_runs": 10, "blocked_runs": 0 },
    "recent_items": []
  }
}
```

## Polling Strategy
| Panel | Interval | Reasoning |
| :--- | :--- | :--- |
| **Remediation Queue** | 5s | Highest volatility; operators need immediate action feedback. |
| **Kernel Status** | 10s | Critical system pulse. |
| **Approval State** | 10s | Timely visibility for manual intervention triggers. |
| **Verification History**| 15s | Moderate volatility; tasks process in batches. |
| **Guardian History** | 15s | Audit trail; usually lags behind execution. |
| **QS Overview** | 20s | Domain logic summary; slower lifecycle. |
| **Policy Drift** | 30s | Lowest volatility; drift occurs over long intervals. |

## Safety Guarantees
- **Pure Projection:** The dashboard acts as a passive read-model.
- **Stateless UI:** No state is held in the UI layer that isn't derived from the Mission Control API.
- **Zero Write Access:** This model specifically excludes write-paths, preventing the UI from accidentally modifying runtime behavior.
