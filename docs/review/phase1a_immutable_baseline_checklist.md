# Phase 1A Immutable Baseline Checklist

Use this checklist for any PR after Phase 1A is merged.

## Protected Baseline Files
- `core/contracts/v1/ref_resolution.map.yaml`
- `core/ref_resolver.py`
- `core/verify/test_ref_resolver.py`

## Rule
Changes to protected baseline files are blocked by default.

## Allowed Exception
Change is allowed only if BOTH are true:
- PR is explicitly labeled `phase1a-override`
- PR includes evidence proving no behavior regression

## Mandatory Reviewer Checks
1. Scope lock:
```bash
git diff --name-only origin/main...HEAD
```
Must NOT include protected baseline files unless override is declared.

2. Proof commands (if protected files touched):
```bash
python3 -m compileall core/ref_resolver.py
python3 core/verify/test_ref_resolver.py
python3 - <<'PY'
from core.ref_resolver import resolve_ref
print(resolve_ref("ref://interface/inbox"))
PY
```

3. Reject conditions:
- Any hardcoded absolute path introduced in resolver/map
- Any unknown-ref behavior changed from fail-closed
- Any files outside declared phase scope

## Suggested Branch Protection Practice
- Require 1 code-owner review for protected baseline files
- Require successful verification checks before merge
- Reject merge on scope mismatch
