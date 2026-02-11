#!/usr/bin/env zsh
set -euo pipefail

cd "${1:-$HOME/0luka}"

echo "== Repo =="
git rev-parse --show-toplevel

echo "\n== Branch/status =="
git status -sb

echo "\n== Fetch remote refs (no changes) =="
git fetch --prune

# If working tree has changes, commit them.
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "\n== Changes detected: committing =="
  git add -A

  # Commit message tuned to your report; adjust if you want.
  git commit -m "phase-o(librarian): harden policy + audit trail (ts_utc) [2026-01-30T19:42:07Z]"
else
  echo "\n== Working tree clean: no commit needed =="
fi

echo "\n== Push current branch =="
branch="$(git branch --show-current)"
git push -u origin "$branch"

echo "\n== Optional tag (safe if rerun) =="
tag="phase-o_sot_hardened_20260130"
if git rev-parse "$tag" >/dev/null 2>&1; then
  echo "Tag already exists: $tag"
else
  git tag -a "$tag" -m "Phase-O: Librarian policy hardened + audited (ts_utc) @ 2026-01-30T19:42:07Z"
  git push origin "$tag"
fi

echo "\n== Done. Final status =="
git status -sb
git log -1 --oneline
