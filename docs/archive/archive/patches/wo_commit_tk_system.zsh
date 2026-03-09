#!/usr/bin/env zsh
# wo_commit_tk_system.zsh — Commit TK system fixes.
# ARCHIVED: One-shot task helper.
set -euo pipefail
ROOT="${ROOT:-$HOME/0luka}"
cd "$ROOT"
# Clean and smoke-test before commit
rm -f "$ROOT/observability/incidents/tk_incidents.jsonl" || true
"$ROOT/system/tools/tk/tk_guard.zsh" || true
git add -A system/tools/tk
git commit -m "feat(tk): emit task_id + tk_task.latest; fix modulectl list parsing"
git push
echo "OK"
