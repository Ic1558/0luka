#!/usr/bin/env zsh
set -euo pipefail

cd ~/02luka

echo "==> Sync main"
git checkout main
git fetch origin
git pull --ff-only origin main

echo
echo "==> Verify files exist in main"
test -f g/docs/PERSONA_MODEL_v5.md && echo "OK: g/docs/PERSONA_MODEL_v5.md"
test -f g/docs/HOWTO_TWO_WORLDS_v2.md && echo "OK: g/docs/HOWTO_TWO_WORLDS_v2.md"
test -f personas/GEMINI_PERSONA_v5.md && echo "OK: personas/GEMINI_PERSONA_v5.md"

echo
echo "==> Cleanup local branches (safe delete if merged)"
git branch -d docs/governance-restore-persona-model-v5 2>/dev/null || true
git branch -d docs/gemini-persona-v5 2>/dev/null || true

echo
echo "==> Cleanup remote branches (only if merged & no longer needed)"
git push origin --delete docs/governance-restore-persona-model-v5 2>/dev/null || true
git push origin --delete docs/gemini-persona-v5 2>/dev/null || true

echo
echo "==> Gemini CLI quick test (expects interactive session)"
echo "When Gemini opens, run:"
echo "  @personas/GEMINI_PERSONA_v5.md"
echo "  @g/docs/PERSONA_MODEL_v5.md"
echo
echo "Launching: env -u GEMINI_API_KEY /opt/homebrew/bin/gemini"
env -u GEMINI_API_KEY /opt/homebrew/bin/gemini
