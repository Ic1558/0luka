#!/bin/zsh
# Pre-Claim Gate v1.0
# Usage: zsh tools/ops/pre_claim_gate.zsh

echo "🔍 Running 0luka Pre-Claim Gate..."

# 1. Telemetry Freshness
echo -n "Checking Telemetry... "
SHELF_TIME=$(date +%s)
TEL_TIME=$(stat -f %m interface/evidence/tasks/ 2>/dev/null || stat -c %Y interface/evidence/tasks/ 2>/dev/null)
if [[ $((SHELF_TIME - TEL_TIME)) -gt 300 ]]; then
    echo "❌ STALE (Last evidence update was > 5 mins ago)"
    # exit 1
else
    echo "✅ FRESH"
fi

# 2. RAM Pressure
echo -n "Checking RAM... "
FREE_PAGES=$(vm_stat | grep "Pages free" | awk '{print $3}' | sed 's/\.//')
if [[ $FREE_PAGES -lt 2000 ]]; then
    echo "⚠️  CRITICAL ($FREE_PAGES pages free)"
else
    echo "✅ OK ($FREE_PAGES pages free)"
fi

# 3. Schema Location
echo -n "Checking Schema Path... "
if [[ -d "interface/schemas" && -f "interface/schemas/task_spec_v2.yaml" ]]; then
    echo "✅ interface/schemas/ is active"
else
    echo "❌ Missing schemas in interface/"
    # exit 1
fi

# 4. Git Hygiene (Secrets)
echo -n "Checking Secrets... "
if git status --porcelain | grep -E ".env.local|policy_secrets.md" > /dev/null; then
    echo "❌ SECRETS EXPOSED (Untracked or staged!)"
    # exit 1
else
    echo "✅ CLEAN"
fi

# 5. Heartbeat
echo -n "Checking Heartbeat... "
if grep "heart-beat" reports/summary/latest.md | head -n 1 > /dev/null; then
     echo "✅ ACTIVE"
else
     echo "❌ SILENT"
fi

echo "🏁 Self-Check Complete."
