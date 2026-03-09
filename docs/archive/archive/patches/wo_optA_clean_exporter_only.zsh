#!/usr/bin/env zsh
# wo_optA_clean_exporter_only.zsh — One-shot task to clean exporter.
# ARCHIVED: Task script for cleaning lac_metrics_exporter.py.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
EXPORTER_PATH="tools/telemetry/lac_metrics_exporter.py"
git checkout main; git reset --hard origin/main
git checkout -b "feat/lac-metrics-exporter-$(date +%y%m%d)"
git add "${EXPORTER_PATH}"
git commit -m "feat(telemetry): add LAC metrics summary exporter"
git push -u origin HEAD
gh pr create --title "feat(telemetry): add LAC metrics summary exporter"
