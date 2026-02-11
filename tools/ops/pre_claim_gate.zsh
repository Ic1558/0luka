#!/bin/zsh
# Pre-Claim Gate v1.0
# Usage: zsh tools/ops/pre_claim_gate.zsh

echo "🔍 Running 0luka Pre-Claim Gate..."

# 1. Telemetry Freshness
echo -n "Checking Telemetry... "
SHELF_TIME=$(date +%s)
# Combine multiple evidence dirs to find the latest update
EVI_DIRS=("interface/evidence/tasks/" "observability/artifacts/tasks/")
LATEST_TEL=0
for d in "${EVI_DIRS[@]}"; do
    if [[ -d "$d" ]]; then
        T=$(stat -f %m "$d" 2>/dev/null || stat -c %Y "$d" 2>/dev/null || echo 0)
        if [[ $T -gt $LATEST_TEL ]]; then LATEST_TEL=$T; fi
    fi
done

if [[ $LATEST_TEL -eq 0 ]]; then
    echo "⚠️  UNKNOWN (No evidence dirs found)"
elif [[ $((SHELF_TIME - LATEST_TEL)) -gt 600 ]]; then
    echo "❌ STALE (Last activity > 10 mins ago)"
    # exit 1
else
    echo "✅ FRESH (Active within 10 mins)"
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
