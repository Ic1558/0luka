#!/usr/bin/env zsh
# verify_persona_v5_after_merge.zsh — One-shot verification for PR #407/408.
# ARCHIVED: Historical verification helper.
set -euo pipefail
cd ~/02luka
git fetch origin
git worktree add -f /tmp/02luka_verify origin/main
cd /tmp/02luka_verify
test -f personas/GEMINI_PERSONA_v5.md && echo "✓ OK: personas/GEMINI_PERSONA_v5.md"
git log --oneline --grep="persona" -5
cd ~/02luka
git worktree remove /tmp/02luka_verify
