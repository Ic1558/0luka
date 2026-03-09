#!/usr/bin/env zsh
# persona_v5_postmerge_sync_test.zsh — One-shot post-merge persona sync test.
# ARCHIVED: Historical test for Persona v5.
set -euo pipefail
cd ~/02luka
git checkout main
git pull --ff-only origin main
test -f personas/GEMINI_PERSONA_v5.md && echo "OK: personas/GEMINI_PERSONA_v5.md"
echo "Launching: gemini CLI test..."
env -u GEMINI_API_KEY /opt/homebrew/bin/gemini
