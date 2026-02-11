# Phase 15.5.3 Spec: Idle/Drift Monitor (SOT-Correct)

## Source of Truth (SOT)

The monitor is **observer-only** and reads a single authoritative JSONL feed.

**Resolution order (no hard paths):**
1. `LUKA_ACTIVITY_FEED_JSONL` (env) — preferred
2. `observability/logs/activity_feed.jsonl` — repo fallback

If the resolved file is missing, unreadable, or contains invalid JSON lines, the monitor must **fail closed** with exit code `4` and must still attempt to emit an error report artifact (see Output Artifacts).

## Constraints (Freeze-safe)

- stdlib only (no external deps)
- observer-only (no network required)
- do **not** modify dispatcher/runtime/gate
- read from logs; write only to `observability/reports/idle_drift_monitor/`

## Configuration (Env)

- `LUKA_ACTIVITY_FEED_JSONL` — path to authoritative JSONL feed (preferred)
- `LUKA_IDLE_THRESHOLD_SEC` — default `900`
- `LUKA_DRIFT_THRESHOLD_SEC` — default `120`

All thresholds are **seconds**.

## Exit Codes

- `0` — OK (no idle/drift detected)
- `2` — WARNING (idle and/or drift detected)
- `4` — ERROR (missing/unreadable log, parse failure, or artifact write failure)

## Output Artifacts (Non-negotiable)

Every run must emit:

- `observability/reports/idle_drift_monitor/<ts>_idle_drift.json`
- `observability/reports/idle_drift_monitor/idle_drift.latest.json` (atomic replace)

Schema:

```json
{
  "schema_version": "idle_drift_report_v1",
  "ts": "2026-02-12T00:00:00Z",
  "source_log": "observability/logs/activity_feed.jsonl",
  "checks": {
    "idle": {
      "ok": true,
      "last_activity_ts": "...",
      "age_sec": 12,
      "threshold_sec": 900
    },
    "drift": {
      "ok": true,
      "last_heartbeat_ts": "...",
      "age_sec": 12,
      "threshold_sec": 120
    }
  },
  "missing": []
}
```

If artifact writing fails, the run must exit `4`.

## Taxonomy Keys (Machine-Stable)

- `idle.system.stale`
- `drift.heartbeat.stale`
- `error.log_missing_or_unreadable`
- `error.log_parse_failure`
- `error.artifact_write_failure`
