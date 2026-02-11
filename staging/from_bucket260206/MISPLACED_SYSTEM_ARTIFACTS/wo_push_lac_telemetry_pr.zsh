#!/usr/bin/env zsh
set -euo pipefail

# Ensure we are at repo root
ROOT="${1:-$PWD}"
cd "$ROOT"

echo "== Preflight =="
git status --porcelain
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD

echo "== Make sure we are up to date =="
git fetch origin

# Create a clean feature branch from current local state
BR="feat/lac-telemetry-$(date +%y%m%d-%H%M%S)"
echo "Creating branch: $BR"
git checkout -b "$BR"

echo "== Prevent auto-generated file from blocking =="
# Keep origin version if present in working tree and ensure it isn't staged
if [[ -f hub/index.json ]]; then
  git restore --source=origin/main -- hub/index.json || true
  git reset -q -- hub/index.json || true
fi

echo "== Verify working tree =="
git status --porcelain

echo "== Push branch =="
git push -u origin "$BR"

echo "== Create PR =="
# Title/body are explicit and short; adjust if you want later
gh pr create \
  --title "feat(telemetry): LAC metrics summary CLI + health check" \
  --body $'Includes:\n- tools/telemetry/lac_metrics_summary.py\n- tools/health/check_mary_to_lac.zsh\n\nNotes:\n- hub/index.json is auto-generated; keep origin version / not part of PR.\n' \
  --base main \
  --head "$BR"

echo "== Done =="
gh pr view || true
