#!/usr/bin/env zsh
# wo_push_lac_telemetry_pr.zsh — Push branch and create LAC telemetry PR.
# ARCHIVED: One-shot PR pusher.
set -euo pipefail
ROOT="${1:-$PWD}"; cd "$ROOT"
BR="feat/lac-telemetry-$(date +%y%m%d-%H%M%S)"
git checkout -b "$BR"
# Restore hub/index.json to origin version to avoid PR pollution
if [[ -f hub/index.json ]]; then
  git restore --source=origin/main -- hub/index.json || true
  git reset -q -- hub/index.json || true
fi
git push -u origin "$BR"
gh pr create \
  --title "feat(telemetry): LAC metrics summary CLI + health check" \
  --body $'Includes:\n- tools/telemetry/lac_metrics_summary.py\n- tools/health/check_mary_to_lac.zsh' \
  --base main --head "$BR"
echo "== Done =="
gh pr view || true
