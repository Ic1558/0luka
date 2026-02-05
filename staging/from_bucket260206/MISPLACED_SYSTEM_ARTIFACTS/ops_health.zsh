#!/usr/bin/env zsh
# Quick ops health check
# Usage: ~/ops_health.zsh

set -euo pipefail

curl -s http://127.0.0.1:4000/api/ops/latest | jq -r '
  "Services: \(.summary.passed)/\(.summary.total) passing" +
  if .summary.failed > 0 then
    "\n⚠️  Failed: " + ([.checks[] | select(.status=="FAIL") | .service] | join(", "))
  else
    "\n✅ All systems operational"
  end
'
