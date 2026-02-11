# Phase 15.5.4 Test Plan: Operational Proof Validation

## 1. Scope
Validation of the transition from Synthetic Proof (manual/tool) to Operational Proof (runtime_auto) for Phase 15.5.3 heartbeats.

## 2. Test Matrix

| Case ID | Scenario | Input / State | Expected Outcome | Missing Key |
|---|---|---|---|---|
| TP_OP_01 | ✅ Operational Pass | All events have `emit_mode: runtime_auto` | `PROVEN` (Exit 0) | None |
| TP_OP_02 | ❌ Synthetic Fail | Mix of `manual_append` or `tool_wrapped` | `PARTIAL` (Exit 2) | `proof.synthetic_not_allowed` |
| TP_OP_03 | ❌ Taxonomy Fail | Missing `ts_epoch_ms` or `run_id` | `PARTIAL` (Exit 2) | `taxonomy.incomplete_event` |
| TP_OP_04 | ❌ Parse Failure | Corrupt `heartbeat.json` | `ERROR` (Exit 4) | N/A (Log Error) |
| TP_OP_05 | ❌ Stale Heartbeat | Heartbeat > 900s old | `PARTIAL` (Exit 2) | `drift.heartbeat.stale` |

## 3. Test Vectors (Data Samples)

### Case TP_OP_01 (Success)
```json
{
  "phase_id": "PHASE_15_5_3",
  "action": "completed",
  "emit_mode": "runtime_auto",
  "verifier_mode": "operational_proof",
  "run_id": "run_fb71",
  "ts_epoch_ms": 1739325600000
}
```

### Case TP_OP_02 (Downgrade)
```json
{
  "phase_id": "PHASE_15_5_3",
  "action": "completed",
  "emit_mode": "manual_append",
  "verifier_mode": "synthetic_proof",
  "ts_epoch_ms": 1739325600000
}
```

## 4. Verification Steps
1. **Mock Runtime**: Run a script that simulates `core/task_dispatcher.py` emitting 3 correctly tagged events.
2. **Run Checker**: `LUKA_REQUIRE_OPERATIONAL_PROOF=1 python3 tools/ops/dod_checker.py --phase PHASE_15_5_3 --json`.
3. **Assert**: Verify `proof_mode` is "operational" and `verdict` is "PROVEN".
4. **Kill Switch**: Set `LUKA_REQUIRE_OPERATIONAL_PROOF=1` and point to a legacy log. Verify `PARTIAL`.

## 5. Acceptance Criteria
- [ ] `dod_checker` correctly identifies `runtime_auto` chains.
- [ ] `dod_report.latest.json` reflects `synthetic_detected: true` for old logs.
- [ ] No regression in performance of `task_dispatcher.py`.
