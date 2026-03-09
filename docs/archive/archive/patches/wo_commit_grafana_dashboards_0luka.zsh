#!/usr/bin/env zsh
# wo_commit_grafana_dashboards_0luka.zsh — Commit Grafana dashboards rename.
# ARCHIVED: One-shot task helper.
set -euo pipefail
cd ~/0luka
git add \
  config/grafana/dashboards/0luka_bossapi_alerts.json \
  config/grafana/dashboards/0luka_bossapi_v2.json \
  config/grafana/dashboards/0luka_prom_am_health.json \
  config/grafana/dashboards/0luka_prometheus_alertmanager_health.json
git commit -m "chore(grafana): rename dashboards to 0luka ids/uids"
git push
echo "OK"
