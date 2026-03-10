#!/usr/bin/env zsh
# Verify Persona v5 files after PR merge
# Usage: Run this AFTER merging PR #408 and #407 in GitHub UI

set -euo pipefail

cd ~/02luka

echo "==> Fetching latest from origin"
git fetch origin

echo
echo "==> Creating worktree to verify origin/main (safe, read-only)"
git worktree add -f /tmp/02luka_verify origin/main

cd /tmp/02luka_verify

echo
echo "==> Verifying files in origin/main"
echo

if test -f g/docs/PERSONA_MODEL_v5.md; then
  echo "✓ OK: g/docs/PERSONA_MODEL_v5.md"
  ls -lh g/docs/PERSONA_MODEL_v5.md
else
  echo "✗ MISSING: g/docs/PERSONA_MODEL_v5.md"
  echo "  → PR #408 may not be merged yet"
fi

echo

if test -f personas/GEMINI_PERSONA_v5.md; then
  echo "✓ OK: personas/GEMINI_PERSONA_v5.md"
  ls -lh personas/GEMINI_PERSONA_v5.md
else
  echo "✗ MISSING: personas/GEMINI_PERSONA_v5.md"
  echo "  → PR #407 may not be merged yet"
fi

echo
echo "==> Checking commit history"
git log --oneline --grep="persona\|PERSONA\|governance.*restore" -5 | head -5

echo
echo "==> Worktree location: /tmp/02luka_verify"
echo "    (Use 'cd ~/02luka && git worktree remove /tmp/02luka_verify' to clean up)"
echo
