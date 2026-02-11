# DoD — PHASE_15_5_1

## Metadata & Revision History
- **Version**: v1.0
- **Edited By**: CLC
- **Date**: 2026-02-12
- **Reason**: DoD for Heartbeat Dropper (PR #21, clec.v1 task generator).

## 0. Metadata (MANDATORY)
- **Phase / Task ID**: PHASE_15_5_1
- **Owner (Actor)**: ops-monitor
- **Gate**: G1
- **Related SOT Section**: §Phase15.5.1
- **Target Status**: DESIGNED → PARTIAL → PROVEN
- **Commit SHA**: d55a50d045e54227b24ebd3aaed4197421e473d3
- **Date**: 2026-02-12

---

## 1. Code State (Static Integrity)
- [ ] Feature implemented (commit referenced)
- [ ] No hard paths (grep verified)
- [ ] Follows `ref://` resolution
- [ ] No decommissioned file modified
- [ ] No test bypass added

---

## 3. Functional Validation (Deterministic Behavior)
- [ ] Generates valid clec.v1 heartbeat task
- [ ] Task passes schema validation
- [ ] Deterministic output (same input = same task shape)
- [ ] No side-effects outside declared scope

---

## 4. Evidence (Fail-Closed Core)
- [ ] Activity event: `started`
- [ ] Activity event: `completed`
- [ ] Activity event: `verified`

### Notes / Links (Evidence pointers)
- **Module**: `modules/ops/phase15_5/`
- **Test Suite**: `core/verify/test_heartbeat_dropper.py`
- **Verification Commands**:
  - `python3 -m pytest core/verify/test_heartbeat_dropper.py -v`
  - `python3 tools/ops/dod_checker.py --phase PHASE_15_5_1 --json`

---

## 5. Negative Testing (Abuse Resistance)
- [ ] Invalid config → rejected or safe default
- [ ] Missing dependencies → fail-closed, no partial task emitted

---

## 7. Gate Check (Non-negotiable)
- [ ] Requires: PHASE_8 (dispatcher must be running to accept heartbeat tasks)
- [ ] Auto-Checker result = **PROVEN**

---

## Verdict
- **DESIGNED**

### Exit Code Expectations
- `dod_checker --phase PHASE_15_5_1`: exit 0 = PROVEN, exit 2 = PARTIAL, exit 3 = DESIGNED
