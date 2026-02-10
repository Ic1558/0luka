# Phase 15.4 DIFF

## Changed
- `skills/manifest.md`
  - Added Phase 15.4 alias reference row for `extra-usage -> verify-first`.
- `core_brain/compiler/skill_wiring.py`
  - Added alias loader from `skills/aliases/aliases_v1.yaml`.
  - Added deterministic normalization and alias resolution.
  - Added explicit unknown/ambiguous alias errors with `requested_id`, `normalized_id`, attempted aliases, and hint.
  - Added provenance emission (`SkillAliasResolver`) on successful alias use.
- `core_brain/compiler/task_enforcer.py`
  - Uses canonical resolved skills for mandatory-read checks to keep interlock enforced after alias resolution.
- `core/verify/test_phase15_4_skill_aliases.py`
  - Added positive, normalization, unknown, ambiguous, provenance, and mandatory-ingest regression cases.

## Added
- `skills/aliases/aliases_v1.yaml`
- `modules/learning_metrics/phase15_4_pr/PLAN.md`
- `modules/learning_metrics/phase15_4_pr/DIFF.md`
- `modules/learning_metrics/phase15_4_pr/VERIFY.md`
