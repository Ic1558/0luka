#!/usr/bin/env zsh
set -euo pipefail

PL_DIR="$HOME/Library/LaunchAgents"
DISABLED_DIR="$HOME/Library/LaunchAgents_disabled"
REPO="$HOME/02luka"
LOGFILE="$REPO/g/reports/launchagents_cleanup.log"

mkdir -p "$DISABLED_DIR"
mkdir -p "$(dirname "$LOGFILE")"

ts(){ date +"%Y%m%d_%H%M%S"; }
TS=$(ts)

echo "=== LaunchAgent Cleanup $(date) ===" | tee -a "$LOGFILE"
echo "" | tee -a "$LOGFILE"

# Get status of all agents (both columns - exit code and PID/status)
declare -A LAST_EXIT
declare -A CURRENT_STATE
while IFS=$'\t' read -r col1 col2 label; do
  [[ -z "$label" || "$label" != com.02luka.* ]] && continue
  LAST_EXIT[$label]=$col1
  CURRENT_STATE[$label]=$col2
done < <(launchctl list | awk 'NR>1 && $3 ~ /^com\.02luka\./ {print $1"\t"$2"\t"$3}')

# Process exit=127 agents (command not found)
echo "🔍 Archiving exit=127 agents (command not found)..." | tee -a "$LOGFILE"
COUNT=0
for plist in "$PL_DIR"/com.02luka.*.plist(N); do
  [[ ! -f "$plist" ]] && continue
  
  label="$(/usr/libexec/PlistBuddy -c 'Print :Label' "$plist" 2>/dev/null || echo "")"
  [[ -z "$label" ]] && continue
  
  # Check both columns for 127
  state="${CURRENT_STATE[$label]:--}"
  last_exit="${LAST_EXIT[$label]:--}"
  
  if [[ "$state" == "127" || "$last_exit" == "127" ]]; then
    echo "  • $label (state=$state)" | tee -a "$LOGFILE"
    
    # Unload first
    launchctl unload "$plist" 2>/dev/null || true
    
    # Archive with timestamp
    archived="$DISABLED_DIR/$(basename "$plist" .plist).${TS}.plist"
    chflags nouchg "$plist" 2>/dev/null || true
    mv -f "$plist" "$archived"
    
    echo "    → Archived to $(basename "$archived")" | tee -a "$LOGFILE"
    ((COUNT++))
  fi
done

# Fix invalid plist (security.scan) if it still exists
INVALID_PLIST="$PL_DIR/com.02luka.security.scan.plist"
if [[ -f "$INVALID_PLIST" ]]; then
  if ! plutil -lint "$INVALID_PLIST" >/dev/null 2>&1; then
    echo "" | tee -a "$LOGFILE"
    echo "🔧 Fixing invalid plist: com.02luka.security.scan" | tee -a "$LOGFILE"
    
    launchctl unload "$INVALID_PLIST" 2>/dev/null || true
    archived="$DISABLED_DIR/com.02luka.security.scan.invalid.${TS}.plist"
    chflags nouchg "$INVALID_PLIST" 2>/dev/null || true
    mv -f "$INVALID_PLIST" "$archived"
    
    echo "  → Archived invalid plist" | tee -a "$LOGFILE"
    ((COUNT++))
  fi
fi

echo "" | tee -a "$LOGFILE"
echo "✅ Cleanup complete" | tee -a "$LOGFILE"
echo "" | tee -a "$LOGFILE"

# Show summary
echo "📊 Summary:" | tee -a "$LOGFILE"
echo "  Archived: $COUNT agents" | tee -a "$LOGFILE"
echo "  Location: $DISABLED_DIR" | tee -a "$LOGFILE"

exit 0
