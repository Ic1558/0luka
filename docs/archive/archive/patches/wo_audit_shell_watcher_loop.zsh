#!/usr/bin/env zsh
# wo_audit_shell_watcher_loop.zsh — one-shot: list shell_watcher launchd labels + tail log
# ARCHIVED: specific to a past shell_watcher incident. Narrow scope, single-use diagnostic.
set -euo pipefail

echo "== Find likely shell_watcher launch agent labels =="
launchctl list | grep -Ei 'shell_watcher|shell-watcher|shellwatcher' || true

echo "\n== Locate plist candidates =="
/usr/bin/grep -rl -- 'shell_watcher' "$HOME/Library/LaunchAgents" 2>/dev/null | sed -n '1,50p' || true

echo "\n== Tail shell_watcher.log =="
logfile="$HOME/02luka/logs/shell_watcher.log"
if [[ -f "$logfile" ]]; then
  tail -n 60 "$logfile" || true
else
  echo "log not found: $logfile"
fi
