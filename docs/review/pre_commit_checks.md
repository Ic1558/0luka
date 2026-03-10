# Pre-Commit Split Checks

Use this to verify branch scope before committing. It is strict and fail-fast.

## Script
- `tools/git/pre_commit_split_check.zsh`

## Typical Usage

### 1) Validate from staged files (current branch)
```zsh
zsh tools/git/pre_commit_split_check.zsh \
  --pattern '^(core/|requirements\.txt$|docs/review/kernel_pr_runbook\.md$)'
```

### 2) Validate from path list file (deterministic)
```zsh
zsh tools/git/pre_commit_split_check.zsh \
  --label feat/v2-kernel-phase1 \
  --file ./kernel_changed.txt \
  --pattern '^(core/|requirements\.txt$|docs/review/kernel_pr_runbook\.md$)'
```

### 3) Three-branch split checks (path-list mode)
```zsh
zsh tools/git/pre_commit_split_check.zsh \
  --label feat/v2-kernel-phase1 \
  --file ./kernel_changed.txt \
  --pattern '^(core/|requirements\.txt$|docs/review/kernel_pr_runbook\.md$)'

zsh tools/git/pre_commit_split_check.zsh \
  --label feat/cole-dropzone \
  --file ./cole_changed.txt \
  --pattern '^(cole/|tests/cole_dropzone_nlp_acceptance\.zsh$)'

zsh tools/git/pre_commit_split_check.zsh \
  --label chore/cleanup-gmx-script \
  --file ./chore_changed.txt \
  --pattern '^(tools/browser_operator_worker\.py$|tools/raycast/|tools/ops/fix_registry_safe\.py$|system/policy/)'
```

## Notes
- Do not use `git add -A` for split PRs.
- Keep `session-ses_3ecb.md` deletion out of split PRs unless intentional and isolated.
- If list files are stale, regenerate before running checks.
