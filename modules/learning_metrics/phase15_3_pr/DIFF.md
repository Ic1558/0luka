# DIFF — Phase 15.3 Pattern-Killer

## Added
- `skills/pattern-killer/SKILL.md`
- `skills/pattern-killer/references/patterns.jsonl`
- `skills/pattern-killer/scripts/pattern_killer.py`
- `core/verify/test_phase15_3_pattern_killer.py`
- `modules/learning_metrics/phase15_3_pr/PLAN.md`
- `modules/learning_metrics/phase15_3_pr/DIFF.md`
- `modules/learning_metrics/phase15_3_pr/VERIFY.md`

## Modified
- `skills/manifest.md`
  - Added exactly one skill row for `pattern-killer`.

## Behavior Summary
- CLI commands: `detect`, `rewrite`, `score`
- Input: `--input-file` or stdin
- Pattern source: JSONL via `--patterns`
- Rewrite apply uses atomic write (`os.replace`)
- Output JSON contains stable score and matched pattern ids
