# PLAN — Phase 15.3 Pattern-Killer

## Intent
Introduce a deterministic local skill `pattern-killer` under `skills/` to support detect/rewrite/score workflows without touching kernel execution paths.

## Scope Lock
Only paths changed:
- `skills/pattern-killer/**`
- `skills/manifest.md` (one row added)
- `core/verify/test_phase15_3_pattern_killer.py`
- `modules/learning_metrics/phase15_3_pr/{PLAN,DIFF,VERIFY}.md`

## Non-Goals
- No changes to `tools/run_tool.zsh`
- No changes to `core_brain/catalog/registry.yaml`
- No core execution wiring changes
- No network behavior

## Design Constraints
- Deterministic CLI output
- JSONL pattern DB with schema/format validation
- Atomic write on rewrite apply (temp + rename)
