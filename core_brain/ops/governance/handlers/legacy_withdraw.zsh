#!/bin/zsh
# 0luka Legacy Withdrawal Handler v1.0
# Targeted for: legacy-bridge group (mary, clc, shell_watcher, etc.)

echo "[LEGACY WITHDRAW] Starting decommissioning process..."

SERVICES=(
    "com.02luka.mary_dispatcher"
    "com.02luka.clc_bridge"
    "com.02luka.clc-bridge"
    "com.02luka.shell_watcher"
    "com.02luka.clc_wo_bridge"
    "com.02luka.auto_wo_bridge_v27"
    "com.02luka.liam_engine"
    "com.02luka.mcp.memory"
)

LAUNCH_AGENT_DIR="$HOME/Library/LaunchAgents"
DISABLED_DIR="$LAUNCH_AGENT_DIR/disabled"
USER_UID="$(id -u)"

disable_plist_guard() {
    local svc="$1"
    local plist="$LAUNCH_AGENT_DIR/$svc.plist"
    if [ -e "$plist" ] || [ -L "$plist" ]; then
        mkdir -p "$DISABLED_DIR"
        local ts
        ts="$(date -u +%Y%m%dT%H%M%SZ)"
        mv "$plist" "$DISABLED_DIR/$svc.plist.disabled.$ts"
        echo "[LEGACY WITHDRAW] Guarded $plist -> $DISABLED_DIR/$svc.plist.disabled.$ts"
    fi
}

# 1. Broad stop/disable via launchctl
for svc in $SERVICES; do
    echo "[LEGACY WITHDRAW] Attempting launchctl bootout/disable for $svc"
    launchctl bootout gui/$USER_UID "$LAUNCH_AGENT_DIR/$svc.plist" 2>/dev/null || \
    launchctl bootout gui/$USER_UID "/Library/LaunchAgents/$svc.plist" 2>/dev/null || \
    launchctl bootout user/$USER_UID "$svc" 2>/dev/null || \
    echo "[LEGACY WITHDRAW] Skip: $svc not found in launchd"
    launchctl disable gui/$USER_UID/$svc 2>/dev/null || true
    disable_plist_guard "$svc"
done

# 2. Force kill any remaining orphan processes
echo "[LEGACY WITHDRAW] Scrubbing orphan processes..."
ps aux | grep -Ei 'mary_dispatcher|clc_bridge|clc-bridge|shell_watcher|clc_wo_bridge|auto_wo_bridge|liam_engine' | grep -v grep | awk '{print $2}' | xargs -n 1 kill -9 2>/dev/null

# 3. Final Check (Process Purity Gate)
COUNT=$(ps aux | grep -Ei 'mary_dispatcher|clc_bridge|clc-bridge|shell_watcher|clc_wo_bridge|auto_wo_bridge|liam_engine' | grep -v grep | wc -l)

if [ "$COUNT" -eq "0" ]; then
    echo "[LEGACY WITHDRAW] SUCCESS: All legacy services withdrawn."
    exit 0
else
    echo "[LEGACY WITHDRAW] FAILURE: $COUNT legacy processes still active."
    exit 1
fi
