#!/bin/zsh
# 0luka Legacy Withdrawal Handler v1.0
# Targeted for: legacy-bridge group (mary, clc, shell_watcher, etc.)

echo "[LEGACY WITHDRAW] Starting decommissioning process..."

SERVICES=(
    "com.02luka.mary_dispatcher"
    "com.02luka.clc_bridge"
    "com.02luka.shell_watcher"
    "com.02luka.clc_wo_bridge"
    "com.02luka.liam_engine"
)

# 1. Broad stop/disable via launchctl
for svc in $SERVICES; do
    echo "[LEGACY WITHDRAW] Attempting launchctl bootout/disable for $svc"
    launchctl bootout gui/$(id -u) "/Library/LaunchAgents/$svc.plist" 2>/dev/null || \
    launchctl bootout user/$(id -u) "$svc" 2>/dev/null || \
    echo "[LEGACY WITHDRAW] Skip: $svc not found in launchd"
done

# 2. Force kill any remaining orphan processes
echo "[LEGACY WITHDRAW] Scrubbing orphan processes..."
ps aux | grep -Ei 'mary_dispatcher|clc_bridge|shell_watcher|clc_wo_bridge|liam_engine' | grep -v grep | awk '{print $2}' | xargs -n 1 kill -9 2>/dev/null

# 3. Final Check (Process Purity Gate)
COUNT=$(ps aux | grep -Ei 'mary_dispatcher|clc_bridge|shell_watcher|clc_wo_bridge|liam_engine' | grep -v grep | wc -l)

if [ "$COUNT" -eq "0" ]; then
    echo "[LEGACY WITHDRAW] SUCCESS: All legacy services withdrawn."
    exit 0
else
    echo "[LEGACY WITHDRAW] FAILURE: $COUNT legacy processes still active."
    exit 1
fi
