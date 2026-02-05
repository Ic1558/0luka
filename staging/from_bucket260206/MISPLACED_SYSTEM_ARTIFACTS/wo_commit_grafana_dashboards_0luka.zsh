#!/usr/bin/env zsh
set -euo pipefail

cd ~/0luka

# Stage ONLY the 4 dashboards (avoid collateral)
git add \
  config/grafana/dashboards/0luka_bossapi_alerts.json \
  config/grafana/dashboards/0luka_bossapi_v2.json \
  config/grafana/dashboards/0luka_prom_am_health.json \
  config/grafana/dashboards/0luka_prometheus_alertmanager_health.json

echo "== staged =="
git diff --cached --name-only

git commit -m "chore(grafana): rename dashboards to 0luka ids/uids"

git push

echo "OK"
