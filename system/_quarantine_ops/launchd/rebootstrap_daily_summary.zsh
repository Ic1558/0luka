#!/usr/bin/env zsh
# rebootstrap_daily_summary.zsh — safely re-bootstrap the daily summary LaunchAgent
# Usage: zsh rebootstrap_daily_summary.zsh
# Safe to re-run. Boots out then re-bootstraps without a plist rewrite.
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.02luka.0luka.daily_summary.plist"
DOMAIN="gui/$(id -u)/com.02luka.0luka.daily_summary"

echo "== sanity =="
echo "user: $(id -un) uid: $(id -u)"
echo "plist: $PLIST"
[[ -f "$PLIST" ]] || { echo "ERROR: plist not found: $PLIST"; exit 1; }

echo ""
echo "== bootout (ignore errors) =="
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null || true

echo ""
echo "== bootstrap =="
launchctl bootstrap "gui/$(id -u)" "$PLIST"

echo ""
echo "== enable =="
launchctl enable "$DOMAIN" || true

echo ""
echo "== kickstart (run once now) =="
launchctl kickstart -k "$DOMAIN" || true

echo ""
echo "== list (confirm loaded) =="
launchctl list | grep -F "com.02luka.0luka.daily_summary" || true

echo ""
echo "== recent log hints =="
echo "If you have a known log path (e.g. build_daily_summary.log), tail it in another tab."
