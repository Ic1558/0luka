# Phase 15.4 PLAN

## Intent
Fix `Unknown skill: extra-usage` with deterministic alias resolution while preserving existing execution semantics.

## Scope Lock
- `skills/manifest.md`
- `skills/aliases/aliases_v1.yaml`
- `core_brain/compiler/skill_wiring.py`
- `core_brain/compiler/task_enforcer.py`
- `core/verify/test_phase15_4_skill_aliases.py`
- `modules/learning_metrics/phase15_4_pr/{PLAN,DIFF,VERIFY}.md`

## Approach
1. Add supplementary alias map under `skills/aliases/aliases_v1.yaml`.
2. Add deterministic normalization: lowercase + `_` to `-`.
3. Resolve alias before wiring checks; reject unknown/ambiguous alias with structured details.
4. Emit provenance row (`tool=SkillAliasResolver`) when alias resolution succeeds.
5. Preserve mandatory-read enforcement after alias resolution via canonical skill IDs.
