#!/usr/bin/env zsh
set -euo pipefail

cd ~/0luka

echo "== precheck =="
git status --porcelain

echo "== stage (only tools/save_now.zsh) =="
git add tools/save_now.zsh

echo "== verify staged =="
git diff --cached --name-only

echo "== commit =="
git commit -m "chore(save-now): finalize plan-phase audit metadata and timeline events"

echo "== push =="
git push

echo "OK"
