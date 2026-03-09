#!/usr/bin/env zsh
# phase4_push.zsh — One-shot Push for Phase 4.
# ARCHIVED: Generic push labeled Phase 4.
set -euo pipefail
cd "$HOME/02luka"
echo "== Branch / HEAD =="
git branch --show-current
git rev-parse --short HEAD
echo "== Push =="
git push -u origin "$(git branch --show-current)"
echo "OK: pushed."
