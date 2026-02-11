# Phase 15.5.4 Test Plan

## Target Tests
- `python3 -m pytest core/verify/test_phase15_5_4_operational_proof.py -q`
- `python3 -m pytest core/verify/test_idle_drift_monitor.py -q`

## Cases
1. Runtime monitor emits operational chain and checker returns PROVEN (exit 0).
2. Synthetic chain under operational-required mode downgrades to PARTIAL with `proof.synthetic_not_allowed`.
3. Missing taxonomy keys downgrades to PARTIAL with `taxonomy.incomplete_event`.

## Manual Verification
- `python3 tools/ops/idle_drift_monitor.py --once --json`
- `LUKA_REQUIRE_OPERATIONAL_PROOF=1 python3 tools/ops/dod_checker.py --phase PHASE_15_5_3 --json`
