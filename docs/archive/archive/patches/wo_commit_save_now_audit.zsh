#!/usr/bin/env zsh
# wo_commit_save_now_audit.zsh — Finalize Save-Now audit commit.
# ARCHIVED: One-shot task helper.
set -euo pipefail
cd ~/0luka
git add tools/save_now.zsh
git commit -m "chore(save-now): finalize plan-phase audit metadata and timeline events"
git push
echo "OK"
