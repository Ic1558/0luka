#!/usr/bin/env zsh
set -euo pipefail

# Safe Git Clean - Only removes ignored files (never untracked workspace)
# Usage:
#   zsh ~/0luka/system/tools/git/safe_git_clean.zsh -n   # Dry-run (ALWAYS DO THIS FIRST)
#   zsh ~/0luka/system/tools/git/safe_git_clean.zsh -f   # Force clean (after reviewing)
#
# Options:
#   -n, --dry-run      Show what would be deleted (DEFAULT, SAFE)
#   -f, --force        Actually delete files (DESTRUCTIVE)
#   -d, --dirs         Include directories
#   -X, --ignored-only Only remove ignored files (DEFAULT, SAFE)

ROOT="${ROOT:-${LUKA_SOT:-${HOME}/0luka}}"
REPO="${ROOT}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SELF="${SCRIPT_DIR}/safe_git_clean.zsh"
GUARD_SCRIPT="${SCRIPT_DIR}/guard_workspace_inside_repo.zsh"

# Color codes for warnings
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

if [[ ! -d "$REPO/.git" ]]; then
  echo "${RED}ERROR: $REPO is not a git repo${NC}" >&2
  exit 1
fi

cd "$REPO"

# Run guard first (warn if workspace is broken, but continue)
echo "${YELLOW}== Pre-clean guard check ==${NC}"
if [[ -x "$GUARD_SCRIPT" ]]; then
  if zsh "$GUARD_SCRIPT" 2>&1 | grep -q "FAIL"; then
    echo "${YELLOW}Warning: Workspace guard detected issues${NC}"
    echo "${YELLOW}   Safe git clean will continue (only removes .gitignore files)${NC}"
    echo ""
  else
    echo ""
    echo "${GREEN}Workspace guard passed${NC}"
    echo ""
  fi
else
  echo "${YELLOW}Guard script not found (${GUARD_SCRIPT}); skipping.${NC}"
  echo ""
fi

echo "${YELLOW}== Safe git clean (only ignored files) ==${NC}"
echo "Using: git clean -fdX (removes only .gitignore-matched files)"
echo ""

# Default to dry-run unless -f is provided
DRY_RUN=1
FORCE=0
DIRS=0
ONLY_IGNORED=1

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -f|--force)
      FORCE=1
      DRY_RUN=0
      shift
      ;;
    -d|--dirs)
      DIRS=1
      shift
      ;;
    -X|--ignored-only)
      ONLY_IGNORED=1
      shift
      ;;
    -n|--dry-run)
      DRY_RUN=1
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [-f] [-d] [-X] [-n]" >&2
      exit 1
      ;;
  esac
done

# Build git clean command
CLEAN_OPTS=""
[[ "$DIRS" -eq 1 ]] && CLEAN_OPTS="${CLEAN_OPTS}d"
[[ "$ONLY_IGNORED" -eq 1 ]] && CLEAN_OPTS="${CLEAN_OPTS}X"
[[ "$DRY_RUN" -eq 1 ]] && CLEAN_OPTS="${CLEAN_OPTS}n"
[[ "$FORCE" -eq 1 ]] && CLEAN_OPTS="${CLEAN_OPTS}f"

if [[ -z "$CLEAN_OPTS" ]]; then
  CLEAN_OPTS="n"  # Default to dry-run
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo "${YELLOW}DRY-RUN MODE (Safe - No files will be deleted)${NC}"
  echo ""
  echo "Files that would be removed:"
  echo ""
  git clean -${CLEAN_OPTS}
  echo ""
  echo "${GREEN}Dry-run complete - No files were deleted${NC}"
  echo ""
  echo "${YELLOW}Next step:${NC}"
  echo "  Review the list above carefully."
  echo "  If you're sure you want to delete these files, run:"
  echo "    ${GREEN}zsh ${SELF} -f${NC}"
else
  echo "${RED}FORCE MODE - Files will be PERMANENTLY DELETED${NC}"
  echo ""
  echo "Command: git clean -${CLEAN_OPTS}"
  echo ""

  # Show what will be deleted
  echo "Files to be deleted:"
  git clean -${CLEAN_OPTS}n
  echo ""

  # Ask for confirmation
  echo -n "${RED}Are you sure you want to DELETE these files? (type 'yes' to confirm): ${NC}"
  read CONFIRM

  if [[ "$CONFIRM" != "yes" ]]; then
    echo ""
    echo "${YELLOW}Cancelled - No files were deleted${NC}"
    exit 0
  fi

  echo ""
  echo "${RED}Deleting files...${NC}"
  git clean -${CLEAN_OPTS}

  echo ""
  echo "${GREEN}Safe clean complete${NC}"
  echo ""
  echo "Note: Only files matching .gitignore patterns were removed."
  echo "      Workspace data in ${HOME}/0luka_ws/ is never touched."
fi
