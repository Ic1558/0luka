# DoD Auto-Checker Specification

## Metadata & Revision History
- **Version**: v1.1
- **Edited By**: GMX (Agentic AI Assistant)
- **Date**: 2026-02-12
- **Reason**: Add governance metadata section for document tracking.

## 1. Objective
Establish an automated, fail-closed mechanism to determine the "Definition of Done" verdict for any Phase. The Checker validates evidence existence and consistency, overriding manual checkboxes.

## 2. Input Integrity
The Checker consumes three sources of truth:
1.  **Activity Feed**: Events with actions `started`, `completed`, `verified`.
2.  **Evidence Artifacts**: Files referenced in events (logs, provenance, hashes).
3.  **Runtime Signals**: Live system state (PID, heartbeat) for daemons.

## 3. Decision Logic (The Verdict)

### 3.1 DESIGNED
-   **Condition**: DoD file exists with valid Metadata.
-   **Missing**: Event `started`.

### 3.2 PARTIAL
-   **Condition**: Event `started` exists.
-   **Missing**: Full evidence chain for PROVEN (e.g., missing `verified` event, missing log file, PID dead).

### 3.3 PROVEN (All Must Pass)
1.  **Activity Chain**: `started` -> `completed` -> `verified` (strictly ordered).
2.  **Evidence Integrity**:
    -   Referenced JSONL logs exist and are readable.
    -   Referenced Provenance hash matches file content (if applicable).
    -   Error logs (last 200 lines) are clean (no FATAL/ERROR unless whitelisted).
3.  **Validation**:
    -   Negative tests recorded in verification evidence.
4.  **Runtime (Daemon Only)**:
    -   PID is alive.
    -   Heartbeat file updated within threshold.
5.  **Gate**:
    -   Prior dependency Phases are PROVEN.

## 4. Output Artifact
path: `observability/reports/dod_status/<phase_id>.json`

```json
{
  "phase_id": "PHASE_15_5_3",
  "verdict": "PARTIAL",
  "timestamp": "2026-02-11T23:59:00Z",
  "checks": {
    "activity_chain": { "started": true, "completed": true, "verified": false },
    "evidence": { "logs_exist": true, "provenance_valid": true, "error_tail_clean": true },
    "runtime": { "pid_alive": false, "heartbeat_fresh": false }
  },
  "missing": ["activity.verified", "runtime.pid_alive"]
}
```

## 5. Anti-Cheat Rules (SOT)
1.  **Checkbox Override**: Manual tick in DoD markdown has **ZERO** effect on the computed Verdict.
2.  **Evidence Reality**: Referencing a non-existent file path = **FAIL**.
3.  **Strict Order**: `verified` event timestamp must be > `completed` > `started`.
