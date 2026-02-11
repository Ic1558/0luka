# OPAL Track A2.1.1 — Observability Pack (DONE)

**Date:** 2026-02-05  
**Repo:** 0luka  
**Phase:** Track A — Multi-host Worker Scaling  
**Status:** ✅ **COMPLETE** — Verified with E2E kill/retry test

---

## Executive Summary

Implemented **A2.1.1 Observability Pack**, a lightweight telemetry system for the A2 distributed scheduler. It captures detailed lifecycle events (lease creation, expiration, reclamation, backoff) in a structured, out-of-band format (JSONL) without impacting the kernel ABI or JobsDB performance.

**Key Value:** Enables detailed debugging of distributed failures and retry behavior without polluting the core job status API.

---

## Scope

### In-Scope
- ✅ **Out-of-band Telemetry:** `observability/telemetry/opal_events.jsonl`
- ✅ **Zero ABI Drift:** No changes to `/api/jobs` response structure.
- ✅ **Structured Logging:** Thread-safe JSONL writer with auto-rotation.
- ✅ **Lifecycle Events:**
  - `lease_created`: Worker claims job
  - `reclaim_winner`: Worker reclaims expired lease (with attribution)
  - `backoff_applied`: Backoff duration and attempt count
  - `retry_scheduled`: Reason for retry
  - `max_retries_reached`: Final failure event

### Out-of-Scope
- ❌ Metrics aggregation (Prometheus/Grafana)
- ❌ Log ingestion piepline (ELK/Splunk)
- ❌ Real-time dashboard

---

## Policy Defaults

| Parameter | Default | Description |
|-----------|---------|-------------|
| `OPAL_TELEMETRY_ENABLED` | `1` (True) | Master switch for telemetry |
| `OPAL_TELEMETRY_MAX_SIZE_MB` | `10` | Max size before rotation |
| `OPAL_EVENTS_LOG_PATH` | `observability/telemetry/opal_events.jsonl` | Log location |

---

## Event Schema

All events share a common envelope:

```json
{
  "ts": "2026-02-05T10:41:50.485515Z",
  "event": "event_name",
  ...payload
}
```

### Event Types

#### 1. `lease_created`
Logged when a worker successfully claims a job and writes a lease file.
```json
{
  "event": "lease_created",
  "job_id": "job_123",
  "worker_id": "host-pid",
  "ttl": 15.0,
  "attempt": 1
}
```

#### 2. `reclaim_winner`
Logged when a worker atomically wins the race to reclaim an expired job.
```json
{
  "event": "reclaim_winner",
  "job_id": "job_123",
  "worker_id": "new-winner-host",
  "prev_worker_id": "dead-host"
}
```

#### 3. `backoff_applied`
Logged when a job is requeued with a delay.
```json
{
  "event": "backoff_applied",
  "job_id": "job_123",
  "attempt": 1,
  "backoff_secs": 8
}
```

#### 4. `retry_scheduled`
Logged along with backoff to indicate retry intent.
```json
{
  "event": "retry_scheduled",
  "job_id": "job_123",
  "attempt": 1,
  "reason": "lease_expired"
}
```

#### 5. `max_retries_reached`
Logged when a job fails permanently after exhausting retries.
```json
{
  "event": "max_retries_reached",
  "job_id": "job_123",
  "final_attempt": 2
}
```

---

## Verification Evidence

### Test Script
`tests/opal_a2_1_1_verify.zsh` performs an E2E test:
1. Submits a job.
2. Identifies and kills the worker holding the lease.
3. Waits for lease expiration and reclamation.
4. Verifies existence and structure of all telemetry events.

### Evidence Artifacts
- **Telemetry Log:** `observability/telemetry/opal_events.jsonl`
- **Verification Output:**
  ```text
  [A2.1.1] ✅ lease_created event found
  [A2.1.1] ✅ reclaim_winner event found
  [A2.1.1] ✅ retry_scheduled event found
  [A2.1.1] ✅ backoff_applied event found
  [A2.1.1] ✅ All events have valid JSON structure
  [A2.1.1] ✅ PASS - Observability Pack working correctly
  ```

---

## Invariants

1. **Non-Blocking:** Telemetry logging must never crash the worker loop. All writes are wrapped in `try/except`.
2. **Atomic Lines:** Each event is a single, complete JSON line (easy for `grep`/`jq`).
3. **Graceful Degradation:** If telemetry fails (disk full, perm error), the job execution continues unaffected.

## Future Work

- **A2.1.2:** Ingest these logs into a standardized structured logging system.
- **A3:** Use these events to drive a "System Health" dashboard showing retry rates and worker churn.

---

**Author:** Antigravity AI Agent  
**Version:** 1.0
