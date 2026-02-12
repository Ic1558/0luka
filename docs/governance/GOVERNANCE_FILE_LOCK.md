# Governance File Lock (Step 2)

## Objective
Prevent silent mutation of governance-critical files while keeping development flow transparent and non-destructive.

## Governance-Critical Scope
- `core/governance/**`
- `docs/dod/**`
- `tools/ops/dod_checker.py`
- `phase_status.yaml` (if present)
- `core/governance/phase_status.yaml`

## Policy
Allowed mutation:
- PR has label `governance-change`.
- Lock manifest `core/governance/governance_lock_manifest.json` is updated in the same change.
- CI checksum verification passes.

Blocked mutation:
- Any critical-file edit without `governance-change`.
- Any critical-file edit without manifest refresh.
- Any critical-file deletion.

## Local Commands (Fail-Closed Sequence)
Read-only first:
```bash
git status --porcelain=v2 --branch
git rev-parse --short HEAD
python3 tools/ops/governance_file_lock.py --verify-manifest --json
```

Backup before change:
```bash
ts=$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "reports/governance_lock_backup_${ts}"
cp core/governance/governance_lock_manifest.json "reports/governance_lock_backup_${ts}/"
git diff -- core/governance docs/dod tools/ops/dod_checker.py core/governance/phase_status.yaml > "reports/governance_lock_backup_${ts}/pre_change.diff"
```

Validate after change:
```bash
python3 tools/ops/governance_file_lock.py --build-manifest --json
python3 tools/ops/governance_file_lock.py --verify-manifest --json
python3 tools/ops/governance_file_lock.py --check-mutation --base origin/main --head HEAD --labels-json '["governance-change"]' --json
```

## CI Integration
- Workflow: `.github/workflows/governance-controls.yml`
- Jobs:
  - `governance-file-lock`
  - `phase-growth-guard`
