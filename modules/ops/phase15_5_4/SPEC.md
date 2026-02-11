# Phase 15.5.4: Operational-Proof Operationalization

## 1. Objective
Establish "Operational Truth" for system heartbeats by transitioning from synthetic/manual log injection to fully automated runtime emissions from the Task Dispatcher.

## 2. Canonical Runtime Hook
- **File Path**: `core/task_dispatcher.py`
- **Rationale**: This file is the central authority for task execution. It already handles `dispatch.start` and `dispatch.end` events and maintains a stable heartbeat file.
- **Safety**: The implementation must use `try/except` blocks to ensure that any failure in activity emission does not block the core dispatch logic (Fail-Open/Non-Blocking).

## 3. Operational Proof Contract (SOT)
### Activity Event Schema
All events emitted during runtime must include:
- `emit_mode`: `runtime_auto`
- `verifier_mode`: `operational_proof`
- `ts_epoch_ms`: High-resolution integer timestamp.
- `run_id`: A UUID or unique string consistent across the `started` -> `completed` -> `verified` chain.

### Anti-Synthetic Rule
- **Target**: `PHASE_15_5_3` (Idle/Drift Monitor)
- **Constraint**: Once Phase 15.5.4 is active, any chain for `PHASE_15_5_3` containing `emit_mode != runtime_auto` MUST be downgraded.
- **Enforcement**: `dod_checker.py` will return `verdict: PARTIAL` with `missing: ["proof.synthetic_not_allowed"]`.

## 4. Governance Guard Enforcement (`dod_checker.py`)
### Enforcement Logic
If `LUKA_REQUIRE_OPERATIONAL_PROOF=1`:
1. Check `phase_id`.
2. Inspect `activity_chain` for `proof_mode`.
3. If `proof_mode == "synthetic"`, force `PARTIAL`.
4. Append `proof.synthetic_not_allowed` to `missing` list.

### Precisions
- Exit codes must remain standard (0=PROVEN, 2=PARTIAL, 3=DESIGNED).
- The enforcement is **opt-in** via environment variable to maintain backward compatibility with legacy phases.

## 5. Monitor Contract (`idle_drift_monitor.py`)
- **Evidence Path**: Must reference the artifact (e.g., `heartbeat.json`) produced or touched by the `runtime_auto` event.
- **Strict Parsing**:
    - If log file is unreadable/corrupt: `EXIT: 4` (Runtime Error).
    - If heartbeat timestamp is older than threshold: `EXIT: 2` (PARTIAL) with `drift.heartbeat.stale`.

## 6. Implementation Checklist (For Codex)
- [ ] Add `emit_activity_event()` utility to `core/timeline.py` or equivalent.
- [ ] Inject hook in `core/task_dispatcher.py`'s `_write_heartbeat`.
- [ ] Update `dod_checker.py` with `LUKA_REQUIRE_OPERATIONAL_PROOF` toggle.
- [ ] Update `idle_drift_monitor.py` to validate `runtime_auto` evidence.
- [ ] Attach `dod_report.latest.json` showing `proof_mode: operational`.
