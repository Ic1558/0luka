# Phase 15.5.3 Spec: Idle/Drift Monitor (MVB)

## Metadata & Revision History
- **Version**: v1.0
- **Edited By**: GMX (Agentic AI Assistant)
- **Date**: 2026-02-12
- **Reason**: Initial design for freeze-safe system observability monitor.

## 1. Objective
Establish a non-invasive daemon/tool that detects if the system has stopped moving (Idle) or if components are diverging from their promised pulse (Drift), for fail-closed diagnosis without modifying core runtime.

## 2. Scope Lock
- **Binary**: `tools/ops/idle_drift_monitor.py`
- **Tests**: `core/verify/test_idle_drift_monitor.py`
- **Authority Logs (Read-Only)**: 
  - `observability/activity/activity.jsonl` (General pulse)
  - `observability/logs/dispatcher.jsonl` (Dispatcher pulse)
- **Output Artifacts**: 
  - `observability/reports/idle_drift_monitor/monitor.latest.json`
  - `observability/reports/idle_drift_monitor/<ts>_monitor.json`

## 3. Decision Logic & Authoritative Logs

### A. Idle Detection (Total System Inactivity)
- **Authoritative Log**: `observability/activity/activity.jsonl`
- **Rule**: `NOW - MAX(ts_all_events) > LUKA_IDLE_THRESHOLD_SEC`
- **Default Threshold**: 900s (15 min)
- **Taxonomy Key**: `idle.system.stale`

### B. Drift Detection (Heartbeat Pulsing)
- **Authoritative Log**: `activity.jsonl` (filtering for `action: heartbeat` or `event: heartbeat`)
- **Rule**: `NOW - MAX(ts_heartbeat) > LUKA_DRIFT_THRESHOLD_SEC`
- **Default Threshold**: 120s (2 min)
- **Taxonomy Key**: `drift.heartbeat.stale`

## 4. Report JSON Schema (`idle_drift_report_v1`)
```json
{
  "schema_version": "idle_drift_report_v1",
  "ts": "2026-02-12T01:30:00Z",
  "status": "OK | WARNING | ERROR",
  "metrics": {
    "last_activity_sec": 45,
    "last_heartbeat_sec": 10,
    "idle_threshold": 900,
    "drift_threshold": 120
  },
  "missing": [],
  "evidence": {
    "feed_path": "observability/activity/activity.jsonl",
    "dispatcher_path": "observability/logs/dispatcher.jsonl"
  }
}
```

## 5. CLI & Exit Codes
- `--once`: Single check and exit.
- `--json`: Output report JSON to stdout.
- `--update-latest`: Atomically update `monitor.latest.json`.
- **Exit Codes (SOT-LOCKED)**:
  - `0`: OK (All pulses fresh)
  - `2`: WARNING (Idle or Drift detected)
  - `4`: ERROR (Cannot read/parse logs or write report)

## 6. Test Vectors (Mock JSONL)
- **Healthy**: Events and heartbeats both sub-10s old.
- **Idle Only**: Last heartbeat 30s ago (OK), but last generic activity 2000s ago (WARNING).
- **Drift Only**: Last generic activity 5s ago (OK), but last heartbeat 600s ago (WARNING).
- **Parse Error**: Feed exists but contains non-JSON junk (ERROR).

## 7. Acceptance Checklist
- [ ] `idle_drift_monitor.py` exists (stdlib only).
- [ ] `LAST_ACTIVITY` logic covers all actions (started, completed, tool_call, etc).
- [ ] `LAST_HEARTBEAT` logic specifically filters for pulse events.
- [ ] Exit codes 0/2/4 verified via test suite.
- [ ] Path traversal guard on log resolution.
- [ ] Atomic write for reports.
