#!/usr/bin/env zsh
set -euo pipefail
cd "$HOME/02luka"

echo "== Branch / HEAD =="
git branch --show-current
git rev-parse --short HEAD

echo "== Remote status =="
git remote -v

echo "== Push =="
git push -u origin "$(git branch --show-current)"

echo "OK: pushed."
