#!/usr/bin/env zsh
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.02luka.0luka.daily_summary.plist"
DOMAIN="gui/$(id -u)/com.02luka.0luka.daily_summary"

echo "== sanity =="
echo "user: $(id -un) uid: $(id -u)"
echo "plist: $PLIST"
[[ -f "$PLIST" ]] || { echo "ERROR: plist not found: $PLIST"; exit 1; }

echo "\n== bootout (ignore errors) =="
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true

echo "\n== bootstrap =="
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo "\n== enable =="
launchctl enable "$DOMAIN" || true

echo "\n== kickstart (run once now) =="
launchctl kickstart -k "$DOMAIN" || true

echo "\n== list (confirm loaded) =="
launchctl list | grep -F "com.02luka.0luka.daily_summary" || true

echo "\n== recent log hints =="
echo "If you have a known log path (e.g. build_daily_summary.log), tail it in another tab."
