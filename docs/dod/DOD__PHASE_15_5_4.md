# DoD — PHASE_15_5_4

## Metadata & Revision History
- **Version**: v1.0
- **Edited By**: CLC
- **Date**: 2026-02-12
- **Reason**: DoD for Operational Proof Enforcement (PR #32, strict mode gate).

## 0. Metadata (MANDATORY)
- **Phase / Task ID**: PHASE_15_5_4
- **Owner (Actor)**: ops-governance
- **Gate**: G1
- **Related SOT Section**: §Phase15.5.4
- **Target Status**: DESIGNED → PARTIAL → PROVEN
- **Commit SHA**: 9544d7f7ac3e63cdf7882f6cad26bead8b3dd797
- **Evidence Path**: observability/reports/phase15_5_4/operational_proof.json
- **Proof Mode**: operational
- **Date**: 2026-02-12

---

## 1. Code State (Static Integrity)
- [ ] Feature implemented (commit referenced)
- [ ] No hard paths (grep verified)
- [ ] No decommissioned file modified
- [ ] No test bypass added

---

## 3. Functional Validation (Deterministic Behavior)
- [ ] `LUKA_REQUIRE_OPERATIONAL_PROOF=1` enables strict mode
- [ ] Synthetic proof_mode → forced PARTIAL (never PROVEN)
- [ ] Missing activity_feed.jsonl → linter raises `ActivityFeedRuntimeError` (exit 4)
- [ ] Taxonomy keys enforced (tool, run_id required in operational mode)
- [ ] Operational proof: all 3 events present + emit_mode=runtime_auto + verifier_mode=operational_proof

---

## 4. Evidence (Fail-Closed Core)
- [ ] Activity event: `started`
- [ ] Activity event: `completed`
- [ ] Activity event: `verified`

### Notes / Links (Evidence pointers)
- **Spec**: `modules/ops/phase15_5_4/SPEC.md`
- **Heartbeat Event Spec**: `modules/ops/phase15_5_4/HEARTBEAT_EVENT_SPEC.md`
- **Test Suite**: `core/verify/test_phase15_5_4_operational_proof.py`
- **Activity Feed Linter**: checked by `dod_checker.py` when `LUKA_REQUIRE_OPERATIONAL_PROOF=1`
- **Fail-Closed Layers**:
  1. Linter: file missing → raise ActivityFeedRuntimeError (exit 4)
  2. Proof Mode: no events → synthetic (cannot be operational)
  3. Verdict Guard: synthetic + strict → force PARTIAL
- **Verification Commands**:
  - `python3 -m pytest core/verify/test_phase15_5_4_operational_proof.py -v`
  - `LUKA_REQUIRE_OPERATIONAL_PROOF=1 python3 tools/ops/dod_checker.py --phase PHASE_15_5_4 --json`
  - `python3 tools/ops/dod_checker.py --phase PHASE_15_5_4 --json`

---

## 5. Negative Testing (Abuse Resistance)
- [ ] Synthetic chain rejected when operational required
- [ ] Missing taxonomy keys flagged
- [ ] Activity feed missing → linter exits 4
- [ ] Out-of-order timestamps → order_ok = false → PARTIAL

---

## 7. Gate Check (Non-negotiable)
- [ ] Requires: PHASE_8 (dispatcher), PHASE_2 (evidence chain)
- [ ] Auto-Checker result = **PROVEN**

---

## Verdict
- **DESIGNED**

### Exit Code Expectations
- `dod_checker --phase PHASE_15_5_4`: exit 0 = PROVEN, exit 2 = PARTIAL, exit 3 = DESIGNED
