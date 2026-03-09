# Phase D Kernel Read Surface Contract

## Scope
Operator read-model for kernel verification layer. This document defines the stable JSON contract for kernel observability within Mission Control.

## Endpoints

### /api/kernel/status
**Description:** Provides a high-level summary of the kernel's health and the presence of critical governance artifacts.

**Response Schema:**
```json
{
  "status": "string (ok|warning)",
  "health": {
    "env_present": "boolean",
    "suite_status": "string (ok|warning)"
  },
  "verification": {
    "recent_verification_count": "integer",
    "guardian_action_count": "integer"
  },
  "artifacts": {
    "epoch_manifest_present": "boolean",
    "rotation_registry_present": "boolean"
  }
}
```

### /api/kernel/verification_history
**Description:** Retrieves a chronological list of recent task verification results.

**Response Schema:**
```json
{
  "items": [
    {
      "trace_id": "string|null",
      "verdict": "string|null (verified|failed)",
      "ts": "string|null (ISO-8601)"
    }
  ]
}
```

### /api/kernel/guardian_history
**Description:** Retrieves a chronological list of recent actions taken by the Runtime Guardian.

**Response Schema:**
```json
{
  "items": [
    {
      "ts": "string|null (ISO-8601)",
      "action": "string|null (allow|freeze_and_alert|...) ",
      "reason": "string|null",
      "trace_id": "string|null",
      "run_id": "string|null",
      "severity": "string|null"
    }
  ]
}
```

## Determinism Guarantees
- **Ordering Guarantees**: Verification history is sorted by file modification time (`st_mtime`) in descending order. Guardian history ordering is determined by the `activity_feed_query` (typically chronological).
- **Field Stability**: Schema keys defined above are frozen and will not be renamed or removed without a major version bump.
- **Safe Degradation**: If truth source directories or files are missing, the endpoints return empty lists (`[]`) or default "warning"/"false" statuses rather than failing.

## Read-Only Guarantees
- **No Mutation Paths**: All helper functions (`load_kernel_status`, etc.) use read-only file access.
- **Method Enforcement**: Endpoints are registered as GET-only. POST, PUT, and DELETE methods are explicitly not handled.
- **Isolation**: No interaction exists with the dispatcher or any state-mutating runtime components.

## Compatibility Guarantee
This contract must remain stable for:
- Mission Control dashboards (React/Vue/Plain HTML)
- Operator CLI tooling
- Future Phase E UI development focusing on approval workflow visibility.

## Non-Claims
- Not an execution interface (cannot trigger runs).
- Not remediation control (cannot clear alerts or manually override gates).
- Not runtime orchestration (does not manage the dispatcher loop).
