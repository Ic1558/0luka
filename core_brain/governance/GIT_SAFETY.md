# Git Safety System

## Critical Warning

**NEVER use `git clean` directly in the 0luka repository!**

Recent incident (2025-12-13): Direct git clean operations deleted critical files including:
- Tools scripts
- Reports and documentation
- System configuration files

## Why Git Clean is Dangerous

```bash
# NEVER DO THIS
git clean -fd        # Deletes ALL untracked files (PERMANENT)
git clean -fdx       # Deletes ALL untracked + ignored files (CATASTROPHIC)
git clean -fdX       # Deletes ignored files (can delete workspace data)
```

**Problems:**
1. **No confirmation** - Deletes immediately
2. **No undo** - Files are PERMANENTLY gone
3. **Not in git history** - Cannot recover
4. **Can wipe workspace** - Loses work-in-progress

## Safe Alternative: safe_git_clean.zsh

### Step 1: Preview (ALWAYS DO THIS FIRST)

```bash
zsh ~/0luka/system/tools/git/safe_git_clean.zsh -n
```

**What it does:**
- Shows what WOULD be deleted (dry-run)
- No files are actually deleted
- Safe to run anytime
- Color-coded output

**Example output:**
```
DRY-RUN MODE (Safe - No files will be deleted)

Files that would be removed:
  __pycache__/
  *.pyc
  .DS_Store

Dry-run complete - No files were deleted

Next step:
  Review the list above carefully.
  If you're sure you want to delete these files, run:
    zsh ~/0luka/system/tools/git/safe_git_clean.zsh -f
```

### Step 2: Clean (After Review)

```bash
zsh ~/0luka/system/tools/git/safe_git_clean.zsh -f
```

**Safety features:**
1. **Workspace guard** - Checks workspace integrity first
2. **Preview** - Shows files before deleting
3. **Confirmation** - Requires typing "yes" to proceed
4. **Restricted scope** - Only deletes .gitignore-matched files
5. **Color warnings** - Red alerts for destructive operations

**Example:**
```
FORCE MODE - Files will be PERMANENTLY DELETED

Files to be deleted:
  __pycache__/
  *.pyc

Are you sure you want to DELETE these files? (type 'yes' to confirm): yes

Deleting files...
Safe clean complete
```

## Setup: Install Git Safety Wrapper

### 1. Add to ~/.zshrc

```bash
# Add this line to your ~/.zshrc
source ~/0luka/system/tools/git/git_aliases.zsh
```

### 2. Reload shell

```bash
source ~/.zshrc
```

### 3. Test

```bash
cd ~/0luka
git clean -n  # Should show warning instead of cleaning
```

## What the Safety Wrapper Does

When you try to run `git clean` in the 0luka directory:

```bash
$ cd ~/0luka
$ git clean -fd

WARNING: Direct 'git clean' is DANGEROUS!

You just tried to run: git clean -fd

This command can PERMANENTLY DELETE:
  - Untracked files
  - Your workspace data
  - Tools and scripts
  - Critical artifacts

SAFE ALTERNATIVE:

  # 1. Preview what will be deleted (ALWAYS DO THIS FIRST):
  zsh ~/0luka/system/tools/git/safe_git_clean.zsh -n

  # 2. After reviewing, delete only ignored files:
  zsh ~/0luka/system/tools/git/safe_git_clean.zsh -f

Aborted to protect your data.
```

## Shell Aliases

If you sourced `git_aliases.zsh`, you have these shortcuts:

```bash
git-safe-clean        # Dry-run preview (safe)
git-safe-clean-force  # Force clean (with confirmation)
```

## How It Works

### 1. safe_git_clean.zsh

**Protections:**
- Workspace guard check (ensures workspace is valid)
- Default to dry-run (never deletes without -f flag)
- Only removes .gitignore-matched files
- Shows preview before deleting
- Requires explicit "yes" confirmation
- Color-coded warnings (red = danger)

**Options:**
- `-n` / `--dry-run` - Preview only (DEFAULT, safe)
- `-f` / `--force` - Actually delete (requires confirmation)
- `-d` / `--dirs` - Include directories
- `-X` / `--ignored-only` - Only .gitignore files (DEFAULT, safe)

### 2. git_aliases.zsh

**Function wrapper:**
```zsh
function git() {
  if [[ "$1" == "clean" && "$PWD" =~ "0luka" ]]; then
    # Show warning instead of running git clean
    zsh ~/0luka/system/tools/git/git_clean_warning.zsh "$@"
  else
    # Normal git command
    command git "$@"
  fi
}
```

**Effect:**
- Intercepts `git clean` in 0luka repo
- Shows safe alternative
- Prevents accidental deletion
- Other git commands work normally

## Emergency: Need to Force Git Clean?

If you REALLY need to run git clean directly (not recommended):

```bash
# Bypass wrapper (DANGEROUS - USE AT YOUR OWN RISK)
/usr/bin/git clean -n   # Preview
/usr/bin/git clean -fd  # Actually clean (PERMANENT DELETION)
```

**Better:** Just use the safe script with confirmation.

## Recovery if Files Are Deleted

If you accidentally deleted files:

### 1. Check git stash
```bash
git stash list
git stash show -p stash@{0}
```

### 2. Check reflog
```bash
git reflog | head -20
git checkout <commit-hash> -- <file-path>
```

### 3. Restore from backup branch
```bash
git checkout v5-core-clean -- <file-path>
```

### 4. Check local backups
```bash
ls -lht ~/0luka_ws/backups/
```

## Best Practices

1. **NEVER use direct `git clean`** in 0luka
2. **ALWAYS run dry-run first** (`-n` flag)
3. **Review the list carefully** before confirming
4. **Use workspace guard** (automatic in safe_git_clean.zsh)
5. **Keep backups** of important work
6. **Commit frequently** so work is in git history

## Related Tools

- `system/tools/git/safe_git_clean.zsh` - Safe clean script
- `system/tools/git/git_clean_warning.zsh` - Warning message
- `system/tools/git/guard_workspace_inside_repo.zsh` - Workspace integrity check (optional)
- `system/tools/git/git_aliases.zsh` - Shell wrapper

## Changelog

**2025-12-13:**
- Created git safety system
- Added safe_git_clean.zsh improvements
- Added git_aliases.zsh wrapper
- Updated system docs with safety protocol
- Added this documentation

**Reason:** Critical files were accidentally deleted using `git reset --hard` + `git clean -fd`

## Questions?

See `CLAUDE.md` (top of file) for quick reference.
