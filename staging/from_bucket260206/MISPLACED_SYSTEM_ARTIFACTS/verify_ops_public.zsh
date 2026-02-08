#!/usr/bin/env zsh
# Verify ops.theedges.work public endpoints
# Usage: ~/verify_ops_public.zsh

set -euo pipefail

echo "🔎 Verifying ops.theedges.work endpoints..."
echo ""

# Test JSON health endpoint
echo "1. ops.latest (JSON health):"
if curl -fsS https://ops.theedges.work/api/ops/latest | jq '.summary'; then
  echo "   ✅ JSON endpoint working"
else
  echo "   ❌ JSON endpoint failed (exit code: $?)"
  echo "   💡 DNS may still be propagating. Try: curl --resolve ops.theedges.work:443:172.67.162.156 -s https://ops.theedges.work/api/ops/latest"
  exit 1
fi

echo ""

# Test HTML dashboard
echo "2. ops.dashboard (HTML UI):"
if TITLE=$(curl -fsS https://ops.theedges.work/api/ops/dashboard | grep -m1 '<title>' | sed 's/^[[:space:]]*//'); then
  echo "   ✅ Dashboard endpoint working"
  echo "   📄 Title: $TITLE"
else
  echo "   ❌ Dashboard endpoint failed"
  exit 1
fi

echo ""
echo "✅ All public endpoints verified successfully"
echo "🌐 Dashboard URL: https://ops.theedges.work/api/ops/dashboard"
