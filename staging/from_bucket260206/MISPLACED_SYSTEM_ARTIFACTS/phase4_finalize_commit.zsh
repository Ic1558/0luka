#!/usr/bin/env zsh
set -euo pipefail

cd "$HOME/02luka"

echo "== Precheck: status =="
git status --porcelain

echo "== Show diffs (02luka.md) =="
git diff -- 02luka.md | sed -n '1,200p'

echo "== Stage files =="
git add 02luka.md g/reports/PHASE4_AUTOMATION_COMPLETE.md

echo "== Commit =="
git commit -m "feat(core-state): phase4 work-notes digest automation + docs + report"

echo "== Postcheck: status =="
git status --porcelain

echo "OK: Phase 4 finalized commit complete."
