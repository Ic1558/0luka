# Manual: Rollback (Safe)

## Principle

Rollback uses `git revert` (creates a new commit that undoes a target commit). This avoids rewriting history.

## Script

- `tools/rollback_git_commit.zsh`

## Usage

```bash
# Revert a specific commit
tools/rollback_git_commit.zsh /path/to/repo <commit-sha>

# Revert HEAD
tools/rollback_git_commit.zsh /path/to/repo HEAD
```

## Safety Checks

- Requires clean worktree before reverting.
