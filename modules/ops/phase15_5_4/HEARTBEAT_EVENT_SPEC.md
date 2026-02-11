# Heartbeat Event Spec (Proposed / Draft)

> **CRITICAL RULE**: "Heartbeat is observability-only and MUST NEVER satisfy started/completed/verified of any phase."

## 1. Scope
This specification defines the "Heartbeat" event schema and emission logic for the Dispatcher runtime. 
- **Status**: Design-only / Proposed.
- **Goal**: Enable `runtime_auto` observability without affecting DoD proof chains.
- **Constraints**: 
    - No modification to `dod_checker.py`, `idle_drift_monitor.py`, or `phase_status.yaml`.
    - Heartbeats must NOT contain `phase` or `phase_id` fields.

## 2. Heartbeat Event Purpose
The heartbeat serves as a system pulse for:
- `idle_drift_monitor` (to detect if the dispatcher is stuck).
- Runtime liveness tracking (uptime, interval consistency).
- Coarse-grained event ordering (via `ts_epoch_ms`).
- **NOT** evidence of task completion. **NOT** a DoD proof artifact.

## 3. Event Schema
The heartbeat event will be appended to `activity_feed.jsonl` with the following structure:

### Required Keys (Machine)
- `ts_utc`: ISO8601 UTC string (e.g., "2026-02-12T12:34:56Z").
- `ts_epoch_ms`: Integer, milliseconds since epoch (High-resolution ordering).
- `category`: "heartbeat" (Stable constant).
- `action`: "heartbeat" (Stable constant).
- `emit_mode`: "runtime_auto" (Signifies automated runtime emission).
- `verifier_mode`: "operational_proof" (Signifies runtime origin, though NOT a DoD proof).
- `actor`: "dispatcher" (or exact runtime component ID).
- `tool`: "task_dispatcher".
- `run_id`: Stable process identifier (e.g., `dispatcher:<boot_time>:<pid>`).
- `host_id`: Stable machine identifier (see Section 4).

### Optional Keys
- `pid`: Integer (Process ID).
- `interval_sec`: Integer (Configured watch interval).
- `heartbeat_seq`: Monotonic counter per process session.
- `meta`: Object (Safe context, no sensitive data).

### Canonical Example
```json
{"ts_utc":"2026-02-12T12:34:56Z","ts_epoch_ms":1770861296000,"category":"heartbeat","action":"heartbeat","emit_mode":"runtime_auto","verifier_mode":"operational_proof","actor":"dispatcher","tool":"task_dispatcher","run_id":"dispatcher:20260212T120000Z:pid73553","host_id":"sha256:ab12...","pid":73553,"heartbeat_seq":42,"interval_sec":60}
```

## 4. Host ID Derivation (Privacy-First)
The `host_id` must be stable but non-sensitive.
- **Format**: `host_id: "sha256:<hex_digest>"`
- **Algorithm**: `SHA256(platform.node())` (Simple) OR `SHA256(platform.node() + ":" + machine_uuid)` (Preferred if available).
- **Constraint**: Do NOT store raw Hardware UUIDs, MAC addresses, or serial numbers. 

## 5. Runtime Hook Candidate
- **File**: `core/task_dispatcher.py`
- **Location**: Inside `_write_heartbeat` (or immediately after), which runs every cycle.
- **Fail-Open Requirement**: The append operation MUST be wrapped in `try/except Exception`. A logging failure must NEVER crash the Dispatcher or stop the heartbeat file update.

## 6. Feed Path Resolution
The emitter must resolve the target log file in this order:
1. Environment variable `LUKA_ACTIVITY_FEED_JSONL`.
2. Default path `observability/logs/activity_feed.jsonl`.
- **Validation**: MUST reject paths containing `..` or targeting non-files.

## 7. Non-Interference Rule (Critical)
To ensure separation from DoD governance:
- **NO** `phase` or `phase_id` keys allowed in heartbeat events.
- **NO** usage of `started`, `completed`, or `verified` in the `action` field.
- **NO** references to DoD evidence paths or artifacts.

## 8. Test Vectors

### ✅ Valid Heartbeat
```json
{"ts_utc": "...", "ts_epoch_ms": 1700000000000, "action": "heartbeat", "category": "heartbeat", "emit_mode": "runtime_auto", "verifier_mode": "operational_proof", "run_id": "...", "host_id": "sha256:..."}
```

### ❌ Invalid (Missing Timestamp)
```json
{"action": "heartbeat", "category": "heartbeat", "emit_mode": "runtime_auto"}
```
*Reason: Cannot perform drift detection without `ts_epoch_ms`.*

### ❌ Invalid (Wrong Emit Mode)
```json
{"action": "heartbeat", "emit_mode": "manual_append"}
```
*Reason: Heartbeats must be operational/runtime_auto.*

### ❌ Invalid (Contains Phase ID - DANGEROUS)
```json
{"action": "heartbeat", "phase_id": "PHASE_15_5_3", "emit_mode": "runtime_auto"}
```
*Reason: Risk of being misinterpreted as a phase activity event.*

## 9. Acceptance Checklist (For Implementation PR)
- [ ] Heartbeat lines are appended by runtime (Codex) without manual/tool edits.
- [ ] `idle_drift_monitor` consumes these lines for drift detection (future update).
- [ ] `dod_checker` ignores these lines for Phase verification (due to missing `phase_id`).
- [ ] No changes to `phase_status.yaml` verdicts occur due to heartbeat emission.
- [ ] Feed remains strictly parseable (JSONL); error handling is robust (quarantine strategy defined).

## 10. Diff Risk Note
**Why this does NOT create synthetic DoD proof:**
Use of `action: "heartbeat"` and EXCLUSION of `phase_id` guarantees that `dod_checker.py` (which filters by `_event_phase_match`) will complete ignore these events. They exist solely for system health monitoring (`idle_drift_monitor`) and operational visibility.
