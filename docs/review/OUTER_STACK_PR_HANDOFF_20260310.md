# Outer Stack PR Handoff

## Branch

- `codex/phase3-8-proof-consumption-ux`

## Included Commits

Oldest to newest:

- `3de64f6` `feat(control-plane): seal mission control read surfaces`
- `911b26e` `fix(runtime): exclude qs jobs from guardian evidence enforcement`
- `8c18dcf` `test(policy): stabilize approval expiry fixture`
- `5b59761` `feat(mission-control): implement operator dashboard ui slice 1`

## Scope

This bounded outer stack covers:

- control-plane read surfaces
- guardian QS exclusion fix
- approval expiry test stabilization
- Mission Control operator dashboard UI slice 1

## What Changed

### Backend / control-plane

- Added sealed Mission Control read surfaces for kernel and operator visibility.
- Added supporting tests and review docs for Phase D and Phase E read-only contracts.

### Runtime guardian safe-scope

- Adjusted guardian evidence enforcement to skip QS job types in safe scope.
- Added verification-chain coverage for the QS exclusion behavior.

### Policy test stabilization

- Stabilized approval expiry fixture logic in `core/verify/test_autonomy_policy.py` to avoid date drift.

### Frontend / UI slice

- Refactored `mission_control.html` to consume the aggregated `/api/operator/dashboard` read model.
- Added UI Slice 1 implementation and seal docs.

## Validation

Read-surface and dashboard slice:

```bash
python3 -m pytest -q \
  core/verify/test_mission_control_kernel_read_surface.py \
  core/verify/test_operator_control_surface.py \
  core/verify/test_operator_dashboard_endpoint.py \
  core/verify/test_mission_control_server.py
```

Result:

- `15 passed`

Guardian slice:

```bash
python3 -m pytest -q \
  core/verify/test_verification_chain.py \
  core/verify/test_runtime_guardian.py
```

Result:

- `8 passed`

Policy test stabilization:

```bash
python3 -m pytest -q core/verify/test_autonomy_policy.py
```

Result:

- `6 passed`

Pre-push stack verification:

```bash
python3 -m pytest -q \
  core/verify/test_mission_control_kernel_read_surface.py \
  core/verify/test_operator_control_surface.py \
  core/verify/test_operator_dashboard_endpoint.py \
  core/verify/test_mission_control_server.py \
  core/verify/test_verification_chain.py \
  core/verify/test_runtime_guardian.py \
  core/verify/test_autonomy_policy.py
```

Result:

- `29 passed`

## Intentionally Held Back

These files are intentionally excluded from the pushed stack and remain isolated in stash:

- `stash@{0}` `hold-back-phase-c-untracked-20260310`
  - `docs/review/PHASE_C_FINAL_VERIFICATION.md`
  - `docs/review/PHASE_C_KERNEL_SLICE_SEAL.md`
  - `docs/review/PHASE_C_POSTFIX_REGRESSION_AUDIT.md`

- `stash@{1}` `hold-back-outer-docs-tracked-20260310`
  - `docs/governance/ESCALATION_MATRIX_DRAFT.md`
  - `docs/governance/FREEZE_0LUKA_PLATFORM_v1.md`
  - `docs/review/pre_commit_checks.md`
  - `implementation_plan.md`
  - `prps/core_architecture.md`
  - `task.md`

These are not part of the pushed stack because they are draft, governance-sensitive, or unrelated to the bounded outer scope above.

## Reviewer Focus

- endpoint/read-surface coherence
- guardian exclusion behavior
- policy test determinism
- UI slice aggregation over `/api/operator/dashboard`

## Non-Claims

This stack does not claim:

- governance freeze-state resolution
- approval/runtime policy redesign
- Phase C documentation closure
- outer platform closure beyond the bounded read-surface and UI slice

## Next Safe Moves

- open PR and review this stack
- restore hold-back docs on a separate cleanup branch later
- continue with Phase F / next backend-ui integration only after review
