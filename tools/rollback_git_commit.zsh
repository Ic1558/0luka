#!/usr/bin/env zsh
set -euo pipefail

REPO_DIR="${1:-}"
TARGET_COMMIT="${2:-HEAD}"

if [[ -z "$REPO_DIR" ]]; then
  echo "Usage: $0 /path/to/git/repo [commit-ish]" >&2
  echo "Example: $0 /Users/icmini/repos/core HEAD" >&2
  exit 2
fi

if [[ ! -d "$REPO_DIR" ]]; then
  echo "[ERR] Repo dir not found: $REPO_DIR" >&2
  exit 3
fi

if ! git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[ERR] Not a git repo: $REPO_DIR" >&2
  exit 4
fi

if [[ -n "$(git -C "$REPO_DIR" status --porcelain=v1)" ]]; then
  echo "[ERR] Working tree not clean; commit or stash first." >&2
  git -C "$REPO_DIR" status --porcelain=v1 >&2
  exit 5
fi

echo "[rollback] repo=$REPO_DIR commit=$TARGET_COMMIT"
git -C "$REPO_DIR" revert --no-edit "$TARGET_COMMIT"
echo "[OK] Revert commit created."
