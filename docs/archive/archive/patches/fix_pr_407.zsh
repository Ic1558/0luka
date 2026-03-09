#!/usr/bin/env zsh
set -euo pipefail

cd ~/02luka
git fetch origin --prune

echo "==> Checkout PR #407 branch"
git checkout docs/gemini-persona-v5

echo "==> Merge origin/main into PR #407 branch (expect conflicts if any)"
git merge origin/main || true

echo
echo "==> If there are conflicts, resolve them now, then run:"
echo "    git status"
echo "    git add -A"
echo "    git commit -m 'merge: resolve conflicts with origin/main'"
echo "    git push -u origin docs/gemini-persona-v5"
echo
echo "Conflicted files (if any):"
git diff --name-only --diff-filter=U || true
