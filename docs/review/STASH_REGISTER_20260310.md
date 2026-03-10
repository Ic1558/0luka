# Stash Register 2026-03-10

## Current Stash List

- `stash@{0}` `hold-back-post-handoff-ui-test-wip-20260310`
- `stash@{1}` `hold-back-post-handoff-ui-wip-20260310`
- `stash@{2}` `hold-back-outer-pr-handoff-20260310`
- `stash@{3}` `hold-back-phase-c-untracked-20260310`
- `stash@{4}` `hold-back-outer-docs-tracked-20260310`
- `stash@{5}` `On ops/phase3-1-8-pr3-rotation-seals: wip-pr3-rotation-seals`
- `stash@{6}` `On codex/phase3-1-1-watchdog-strictness: wip-split-20260303T200811Z`
- `stash@{7}` `On codex/plan-c-purity-finalize: park: test_config pending before docs-only PR`
- `stash@{8}` `On codex/plan-c-purity-finalize: freeze12h-prep: park dirty worktree before PlanC freeze`

## Classification

- `stash@{0}`: `MANUAL_REVIEW_REQUIRED`
  - UI test WIP stash with unclear tracked-file surface in summary output; inspect before any drop decision.

- `stash@{1}`: `KEEP_FOR_FUTURE_WORK`
  - Mission Control UI follow-up WIP on the same dashboard surface as the merged UI slices.

- `stash@{2}`: `SAFE_TO_DROP_LATER`
  - Outer PR handoff residue; the handoff doc was already committed and pushed.

- `stash@{3}`: `ARCHIVE_REFERENCE_ONLY`
  - Historical Phase C review/doc material kept for reference, not active work.

- `stash@{4}`: `KEEP_FOR_FUTURE_WORK`
  - Governance/planning hold-back set that should remain isolated until intentionally revisited.

- `stash@{5}`: `REVIEW_LATER`
  - Small unrelated ops/runtime WIP centered on rotation seals; not urgent, not part of current branch closeout.

- `stash@{6}`: `MANUAL_REVIEW_REQUIRED`
  - Broad mixed code/tools stash spanning core and ops; too substantial to drop without inspection.

- `stash@{7}`: `REVIEW_LATER`
  - Narrow single-test stash that can be evaluated later without urgency.

- `stash@{8}`: `MANUAL_REVIEW_REQUIRED`
  - Mixed test/docs/tools stash with both transient notes and code-bearing content.

## Recommended Handling Order

1. Preserve active future-work stashes:
   - `stash@{1}`
   - `stash@{4}`
2. Preserve archive reference stash:
   - `stash@{3}`
3. Leave review-required stashes untouched until a dedicated cleanup pass:
   - `stash@{0}`
   - `stash@{6}`
   - `stash@{8}`
4. Review later when convenient:
   - `stash@{5}`
   - `stash@{7}`
5. Drop only after explicit confirmation in a later pass:
   - `stash@{2}`
