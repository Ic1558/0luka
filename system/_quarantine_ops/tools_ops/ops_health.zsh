#!/usr/bin/env zsh
# ops_health.zsh — quick ops health check against local API
# Usage: zsh tools/ops/ops_health.zsh
# Hits http://127.0.0.1:4000/api/ops/latest and prints pass/fail summary.
set -euo pipefail

curl -s http://127.0.0.1:4000/api/ops/latest | jq -r '
  "Services: \(.summary.passed)/\(.summary.total) passing" +
  if .summary.failed > 0 then
    "\n⚠️  Failed: " + ([.checks[] | select(.status=="FAIL") | .service] | join(", "))
  else
    "\n✅ All systems operational"
  end
'
