# Stash Register 2026-03-10

Current stash inventory at outer-repo root. This note is operational memory only.

## Current Stashes

- `stash@{0}` `park-phase-cd-recovery-20260310`
  - Classification: `KEEP_FOR_FUTURE_WORK`
  - Reason: parked Phase C/D recovery files require broader historical lineage and must remain isolated from the clean A+B branch.

- `stash@{1}` `hold-back-post-handoff-ui-test-wip-20260310`
  - Classification: `MANUAL_REVIEW_REQUIRED`
  - Reason: UI test WIP with unclear remaining value after the merged UI slice line.

- `stash@{2}` `hold-back-post-handoff-ui-wip-20260310`
  - Classification: `KEEP_FOR_FUTURE_WORK`
  - Reason: post-handoff Mission Control UI follow-up work, still potentially useful for later UI continuation.

- `stash@{3}` `hold-back-outer-pr-handoff-20260310`
  - Classification: `SAFE_TO_DROP_LATER`
  - Reason: PR handoff note was already committed and pushed.

- `stash@{4}` `hold-back-phase-c-untracked-20260310`
  - Classification: `ARCHIVE_REFERENCE_ONLY`
  - Reason: historical Phase C review/docs material; keep only as reference.

- `stash@{5}` `hold-back-outer-docs-tracked-20260310`
  - Classification: `KEEP_FOR_FUTURE_WORK`
  - Reason: governance/planning hold-back set; should stay isolated until intentionally revisited.

- `stash@{6}` `wip-pr3-rotation-seals`
  - Classification: `REVIEW_LATER`
  - Reason: unrelated ops/runtime WIP, not part of the current bounded branch work.

- `stash@{7}` `wip-split-20260303T200811Z`
  - Classification: `MANUAL_REVIEW_REQUIRED`
  - Reason: broad mixed core/tools stash; too risky to drop without a dedicated forensic pass.

- `stash@{8}` `park: test_config pending before docs-only PR`
  - Classification: `REVIEW_LATER`
  - Reason: small single-test stash, low urgency but not obviously obsolete.

- `stash@{9}` `freeze12h-prep: park dirty worktree before PlanC freeze`
  - Classification: `MANUAL_REVIEW_REQUIRED`
  - Reason: mixed test/docs/tools stash; requires separate review before any cleanup.

## Recommended Handling Order

1. Keep intact:
   - `stash@{0}`
   - `stash@{2}`
   - `stash@{5}`

2. Keep as archive/reference:
   - `stash@{4}`

3. Review later in dedicated passes:
   - `stash@{6}`
   - `stash@{8}`

4. Manual review before any destructive action:
   - `stash@{1}`
   - `stash@{7}`
   - `stash@{9}`

5. Safe drop candidate only after confirmation:
   - `stash@{3}`
