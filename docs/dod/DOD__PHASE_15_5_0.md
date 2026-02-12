# DoD — PHASE_15_5_0

## Metadata & Revision History
- **Version**: v1.0
- **Edited By**: CLC
- **Date**: 2026-02-12
- **Reason**: DoD for GitHub Preflight Network Gate (PR #23).

## 0. Metadata (MANDATORY)
- **Phase / Task ID**: PHASE_15_5_0
- **Owner (Actor)**: ops-monitor
- **Gate**: G1
- **Related SOT Section**: §Phase15.5.0
- **Target Status**: DESIGNED → PARTIAL → PROVEN
- **Commit SHA**: 7d3bd6dc411371c6198feeca6d2596812083e333
- **Evidence Path**: observability/reports/phase15_5_0/preflight_github.json
- **Proof Mode**: operational
- **Date**: 2026-02-12

---

## 1. Code State (Static Integrity)
- [ ] Feature implemented (commit referenced)
- [ ] No hard paths (grep verified)
- [ ] No decommissioned file modified
- [ ] No test bypass added

---

## 2. Runtime State (Process Truth)
- [ ] Script exits 0 on all-clear, exits 1 on any failure
- [ ] No infinite loops or hangs (timeouts set: ping -W 5, curl --max-time 10)

---

## 3. Functional Validation (Deterministic Behavior)
- [ ] DNS check: `ping github.com` pass/fail
- [ ] API check: `curl api.github.com` pass/fail
- [ ] Auth check: `gh auth status` pass/fail
- [ ] Partial failure reported (one check fails, others still run)

---

## 4. Evidence (Fail-Closed Core)
- [ ] Activity event: `started`
- [ ] Activity event: `completed`
- [ ] Activity event: `verified`

### Notes / Links (Evidence pointers)
- **Tool**: `tools/ops/preflight_github.zsh`
- **Verify Doc**: `modules/ops/phase15_5_0_preflight/VERIFY.md`
- **Verification Commands**:
  - `./tools/ops/preflight_github.zsh; echo $?`
  - `LUKA_REQUIRE_OPERATIONAL_PROOF=1 python3 tools/ops/dod_checker.py --phase PHASE_15_5_0 --json`
  - `python3 tools/ops/dod_checker.py --phase PHASE_15_5_0 --json`

---

## 5. Negative Testing (Abuse Resistance)
- [ ] Network down → DNS FAIL reported, exits 1
- [ ] Auth expired → gh auth FAIL reported, exits 1

---

## 7. Gate Check (Non-negotiable)
- [ ] No prerequisite phases required (standalone ops gate)
- [ ] Auto-Checker result = **PROVEN**

---

## Verdict
- **DESIGNED**

### Exit Code Expectations
- `dod_checker --phase PHASE_15_5_0`: exit 0 = PROVEN, exit 2 = PARTIAL, exit 3 = DESIGNED
