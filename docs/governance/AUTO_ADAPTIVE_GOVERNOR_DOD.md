# Auto-Adaptive Governor Router — DoD

## Scope
- Contract SOT: `core/governance/auto_governor_contract.yaml`
- Router CLI: `tools/ops/auto_governor_router.py`
- Tests: `core/verify/test_auto_governor_router.py`
- CI gate: `.github/workflows/governor-router.yml`

## CLI Behavior (v0)
- Input modes:
  - `--nl <text>` for natural language inference
  - `--proposed-paths <path...>` for explicit path classification
- Output:
  - `--json` returns deterministic JSON with fields:
    - `mode`, `ring`, `risk`
    - `allowed_mutations`, `required_checks`, `required_labels`
    - `command_plan`, `exit_code`, `reason`
- Exit codes:
  - `0`: valid routing result
  - `2`: partial (reserved by contract)
  - `3`: designed / approval required (reserved by contract)
  - `4`: contract violation / unknown scope / invalid input

## Governance Constraints
- Fail-closed:
  - Unknown scope -> exit `4`
  - Missing input (`--nl` and `--proposed-paths` absent) -> exit `4`
- Forbidden patterns enforced by contract:
  - Governance hard-path pattern in governance scopes
  - Unauthorized `DELETE` operation in protected scopes
- No write-back behavior:
  - Router only classifies and outputs plan/decision

## DoD Checklist
- Functional:
  - `core/` or `.github/workflows/` -> `HARD`, `R3`, `Critical`
  - `core_brain/` or `tools/ops/` -> `MED`, `R2`, `High`
  - module paths (`modules/`, `skills/`, `interface/`) -> `MED`, `R1`, `Medium`
  - artifact/doc paths (`docs/`, `reports/`, `observability/`) -> `SOFT`, `R0`, `Low`
- Safety:
  - Unknown path returns exit `4`
  - Forbidden hard-path/delete scenarios return exit `4`
- Tests:
  - `python3 -m pytest core/verify/test_auto_governor_router.py -q` passes
  - `python3 -m pytest core/verify/test_governance_contract.py -q` passes
- CI:
  - workflow `auto-governor-router` succeeds on PR
  - `HARD` mode PR requires `governance-change` label

## Local Verification
```bash
python3 tools/ops/auto_governor_router.py --proposed-paths core/governance/agents.md --json ; echo EXIT:$?
python3 tools/ops/auto_governor_router.py --proposed-paths docs/readme.md --json ; echo EXIT:$?
python3 tools/ops/auto_governor_router.py --proposed-paths /unknown/random/path.txt --json ; echo EXIT:$?
python3 -m pytest core/verify/test_auto_governor_router.py -q
python3 -m pytest core/verify/test_governance_contract.py -q
```
