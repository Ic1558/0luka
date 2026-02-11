#!/usr/bin/env zsh
set -euo pipefail

ROOT="$HOME/02luka"
BRANCH="chore/mls-runtime-only"
MSG="chore(mls): treat MLS outputs as runtime-only (ignore + untrack)"

cd "$ROOT"

echo "==> Ensure clean base"
git fetch origin
git checkout main
git reset --hard origin/main

echo "==> Create branch: $BRANCH"
git checkout -b "$BRANCH"

echo "==> Verify expected changes only"
git status --short

# Safety check: allow only these paths
ALLOWED=(
  ".gitignore"
  "g/knowledge/mls_index.json"
  "g/knowledge/mls_lessons.jsonl"
)

CHANGED=$(git status --porcelain | awk '{print $2}')
for f in $CHANGED; do
  if ! printf '%s\n' "${ALLOWED[@]}" | grep -qx "$f"; then
    echo "ERROR: unexpected changed file: $f"
    exit 1
  fi
done

echo "==> Commit"
git add .gitignore
git rm --cached g/knowledge/mls_index.json g/knowledge/mls_lessons.jsonl
git commit -m "$MSG"

echo "==> Push"
git push -u origin "$BRANCH"

echo ""
echo "==> Open PR"
gh pr create \
  --title "$MSG" \
  --body $'Policy A:\n- MLS outputs are runtime-only\n- Ignore via .gitignore\n- Untrack from git index\n\nData lives in ~/02luka_ws/g/knowledge/\nNo symlinks committed.' \
  --base main \
  --head "$BRANCH"

echo ""
echo "==> Done. PR created."
