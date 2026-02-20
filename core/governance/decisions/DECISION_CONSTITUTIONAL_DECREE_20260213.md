# DECISION: Constitutional Governance Architecture (Core Is Law)

## Status
- decision_id: DECISION_CONSTITUTIONAL_DECREE_20260213
- state: ACTIVE
- mode: FAIL_CLOSED
- effective_date_utc: 2026-02-13T00:00:00Z

## Constitutional Principle
- Core is law (`core/governance/**`).
- 0luka executes law (`core_brain/**`, `tools/ops/**`, runtime lanes).

## Enforcement Artifacts
- Machine contract: `core/governance/separation_of_powers.yaml`
- Constitutional decree: `core/governance/CONSTITUTIONAL_DECREE.md`
- Governance contract tests: `core/verify/test_governance_contract.py`

## Redirect Decisions
- `core_brain/ops/governance/gate_runnerd.py` must use canonical ontology at:
  - `core/governance/ontology.yaml`
- `core_brain/governance/soul.md` renamed to:
  - `core_brain/governance/agent_soul.md`

## Duplicate Source Policy
- Forbidden duplicate copies in `core_brain/governance/` for:
  - `prps.md`
  - `ontology.yaml`
- Canonical sources remain in `core/governance/`.

## Notes
- This decision does not alter ABI contract (`core/governance/tier3_abi.yaml`).
- This decision does not alter checker logic in `tools/ops/dod_checker.py`.
