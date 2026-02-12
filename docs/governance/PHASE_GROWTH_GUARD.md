# Phase Growth Guard (Step 3)

## Objective
Ensure new phase/module growth is reproducible and fail-closed.

## Enforced Rules
- Phase ID format must match `^PHASE_[A-Z0-9_]+$`.
- New phase DoD file must live at `docs/dod/DOD__<PHASE_ID>.md`.
- New phase requires:
  - Registry entry in `core/governance/phase_status.yaml`
  - Test stub `core/verify/test_<phase_id_lower>.py`
  - Proof harness `core/verify/prove_<phase_id_lower>.py`
- New module directory name under `modules/` must match `^[a-z0-9][a-z0-9_-]*$`.
- New module must include `modules/<name>/README.md`.

## Controlled Spawner
- Generator: `tools/ops/phase_template_generator.py`
- Guard validator: `tools/ops/phase_growth_guard.py`

## Local Preflight
Check introduced phases/modules in current branch:
```bash
python3 tools/ops/phase_growth_guard.py --check-diff --base origin/main --head HEAD --json
```

Generate deterministic scaffold (dry-run):
```bash
python3 tools/ops/phase_template_generator.py --phase PHASE_16_0 --owner "TBD" --gate "TBD" --dry-run
```

Generate deterministic scaffold (apply):
```bash
python3 tools/ops/phase_template_generator.py --phase PHASE_16_0 --owner "TBD" --gate "TBD"
```

## Pass/Fail Examples
Pass:
- `docs/dod/DOD__PHASE_16_0.md` exists
- `core/governance/phase_status.yaml` has `PHASE_16_0`
- `core/verify/test_phase_16_0.py` exists
- `core/verify/prove_phase_16_0.py` exists

Fail:
- Missing proof harness -> guard exits non-zero
- Invalid module name (example `modules/Bad-Name`) -> guard exits non-zero
