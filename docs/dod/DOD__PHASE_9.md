# DoD — PHASE_9

## Metadata & Revision History
- **Version**: v1.0
- **Edited By**: GMX (Agentic AI Assistant)
- **Date**: 2026-02-12
- **Reason**: Initial creation of SOT-locked DoD for Phase 9.

## 0. Metadata (MANDATORY)
- **Phase / Task ID**: PHASE_9
- **Owner (Actor)**: nlp_engine
- **Gate**: G9
- **Related SOT Section**: §Tier1.Phase9
- **Target Status**: DESIGNED → PARTIAL → PROVEN
- **Commit SHA**: 0a79adcc080d68ecfccf407680a41c2f6d242ac8
- **Evidence Path**: observability/reports/nlp/task_shape_audit.json
- **Proof Mode**: operational
- **Date**: 2026-02-12

## 4. Evidence (Fail-Closed Core)
- [ ] Activity event: `started`
- [ ] Activity event: `completed`
- [ ] Activity event: `verified`

### Notes / Links (Evidence pointers)
- **Expected Activity Pattern**: 
  - `action: started`, `phase_id: PHASE_9`
  - `action: completed`, `phase_id: PHASE_9`, `evidence: ["observability/reports/nlp/task_shape_audit.json"]`
  - `action: verified`, `phase_id: PHASE_9`
- **Primary Evidence Artifacts**:
  - `core/contracts/v1/task_schemas.json`
  - `observability/reports/nlp/task_shape_audit.json`
- **Verification Command**: `python3 core/verify/prove_phase9_nlp.py`
- **Strict Expectation**:
  - `LUKA_REQUIRE_OPERATIONAL_PROOF=1`
  - `proof_mode: operational`
  - `synthetic_detected: false`
  - `taxonomy_ok: true`
  - `exit: 0`
