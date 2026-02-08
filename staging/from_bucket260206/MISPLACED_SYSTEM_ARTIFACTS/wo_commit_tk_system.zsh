#!/usr/bin/env zsh
set -euo pipefail

cd "$HOME/0luka"
ROOT="${ROOT:-$HOME/0luka}"

echo "== precheck: tk_guard smoke =="
rm -f "$ROOT/observability/incidents/tk_incidents.jsonl" || true
ROOT="$ROOT" "$ROOT/system/tools/tk/tk_guard.zsh" || true

echo "== git status (porcelain) =="
git status --porcelain

echo "== stage tk system only =="
git add -A system/tools/tk

echo "== verify staged =="
git diff --cached --name-status

echo "== commit =="
git commit -m "feat(tk): emit task_id + tk_task.latest; fix modulectl list parsing"

echo "== push =="
git push

echo "OK"
