# DoD — PHASE_15_4

## Metadata & Revision History
- **Version**: v1.1
- **Edited By**: CLC
- **Date**: 2026-02-12
- **Reason**: Add covered sub-phases 15.1 + 15.2 per Decision_Phase15x_Classification_260212.md.

## 0. Metadata (MANDATORY)
- **Phase / Task ID**: PHASE_15_4
- **Owner (Actor)**: skill-os
- **Gate**: G15
- **Related SOT Section**: §Tier2.Phase15.4
- **Target Status**: DESIGNED → PARTIAL → PROVEN
- **Commit SHA**: d53b02190eea90ad874fda25f8f2e1d765adf864
- **Date**: 2026-02-12

---

## Covered Sub-Phases (Consolidated)

This DoD covers 3 facets of the same compiler gate (`task_enforcer.validate_plan_report()`):

| Sub-Phase | Facet | Test File |
|-----------|-------|-----------|
| **15.1** (Skill Wiring) | Mandatory read enforcement — "did you ingest the skill context?" | `core/verify/test_phase15_1_skill_wiring.py` |
| **15.2** (Codex Wiring) | Execution contract validation — "do you have caps, preamble, retry?" | `core/verify/test_phase15_2_codex_wiring.py` |
| **15.4** (Skill Aliases) | Deterministic alias resolution — "css" → "tailwind-css-expert" | `core/verify/test_phase15_4_skill_aliases.py` |

**Classification source**: `Decision_Phase15x_Classification_260212.md` (SOT)

---

## 3. Functional Validation (Deterministic Behavior)
- [ ] 15.1: Missing mandatory read → plan rejected (fail-closed)
- [ ] 15.1: Present mandatory read + skill ingest → plan passes + provenance emitted
- [ ] 15.2: Missing execution_contract → plan rejected (fail-closed)
- [ ] 15.2: Invalid manifest wiring → `skill_wiring_invalid` rejection
- [ ] 15.2: Valid contract + wiring → plan passes + provenance emitted
- [ ] 15.4: Alias resolves to canonical ID deterministically
- [ ] 15.4: Unknown alias → fail-closed rejection

---

## 4. Evidence (Fail-Closed Core)
- [ ] Activity event: `started`
- [ ] Activity event: `completed`
- [ ] Activity event: `verified`

### Notes / Links (Evidence pointers)
- **Expected Activity Pattern**:
  - `action: started`, `phase_id: PHASE_15_4`
  - `action: completed`, `phase_id: PHASE_15_4`, `evidence: ["observability/reports/skills/phase15_4_aliases.json"]`
  - `action: verified`, `phase_id: PHASE_15_4`
- **Primary Evidence Artifacts**:
  - `core/verify/test_phase15_4_skill_aliases.py` (alias resolution)
  - `core/verify/test_phase15_1_skill_wiring.py` (mandatory read)
  - `core/verify/test_phase15_2_codex_wiring.py` (execution contract)
  - `observability/reports/skills/phase15_4_aliases.json`
- **Core Module**: `core_brain/compiler/task_enforcer.py`
- **Alias Module**: `core_brain/compiler/skill_wiring.py`
- **Verification Commands**:
  - `python3 -m pytest core/verify/test_phase15_4_skill_aliases.py core/verify/test_phase15_1_skill_wiring.py core/verify/test_phase15_2_codex_wiring.py -v`
  - `python3 tools/ops/dod_checker.py --phase PHASE_15_4 --json`

---

## 7. Gate Check (Non-negotiable)
- [ ] No prerequisite phases required
- [ ] Auto-Checker result = **PROVEN**

---

## Verdict
- **PROVEN**

### Exit Code Expectations
- `dod_checker --phase PHASE_15_4`: exit 0 = PROVEN, exit 2 = PARTIAL, exit 3 = DESIGNED
