<!--
Step 15501 Verify: Phase 15.5.2 Heartbeat
-->
# Verification Steps (Phase 15.5.2)

## 1. Automated Tests
Run the specific test suite:
```bash
python3 -m pytest core/verify/test_phase15_5_2_timeline_heartbeat.py -q
```
**Expected**: Pass (3 tests: happy path emit, exception handling, rejected tasks).

## 2. Regression Tests
Run core verification:
```bash
python3 -m pytest core/verify -q
```
**Expected**: Pass (no regressions in dispatcher logic).

## 3. Health Check
Run full health check:
```bash
python3 core/health.py --full
```
**Expected**: All checks pass (dispatcher remains healthy).
