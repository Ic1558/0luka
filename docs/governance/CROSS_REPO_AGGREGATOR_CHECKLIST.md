# Cross-Repo Aggregator v0 Checklist (Step 4 Prep)

## Scope
Prepare multi-repo governance visibility without enabling execution in this step.

## Inputs to Standardize
- `core/governance/phase_status.yaml` path per repo
- default branch ref (typically `main`)
- repository identity (`owner/repo`)
- artifact root path for DoD evidence

## Output Contract (Draft)
- Table columns:
  - `repo`
  - `phase`
  - `verdict`
  - `commit_sha`
  - `evidence_path`
  - `proof_mode`
  - `updated_at`

## Validation Checks
- Missing `phase_status.yaml` -> report `MISSING_REGISTRY`
- Invalid YAML schema -> report `SCHEMA_ERROR`
- Same phase conflicting verdicts across repos -> report `CROSS_REPO_CONFLICT`
- Dependency mismatch against declared `requires` -> report `DEPENDENCY_MISMATCH`

## Rollout Gate
- Aggregator read-only mode first
- No writeback to source repos
- Evidence snapshots retained per run
- Exit non-zero on schema/dependency conflicts
