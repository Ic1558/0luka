#!/usr/bin/env zsh
set -euo pipefail

PLIST="$HOME/Library/LaunchAgents/com.02luka.mls-symlink-guard.plist"
PY="/usr/bin/python3"
ROOT="/Users/icmini/02luka"
SCRIPT="$ROOT/tools/guardrails/mls_symlink_guard.py"
LOG_DIR="/Users/icmini/02luka_ws/g/telemetry"
STDOUT_LOG="$LOG_DIR/mls_symlink_guard.stdout.log"
STDERR_LOG="$LOG_DIR/mls_symlink_guard.stderr.log"

mkdir -p "$LOG_DIR"

if [[ ! -f "$SCRIPT" ]]; then
  echo "ERROR: missing $SCRIPT" >&2
  exit 1
fi

cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.02luka.mls-symlink-guard</string>

  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$SCRIPT</string>
  </array>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>ThrottleInterval</key>
  <integer>10</integer>

  <key>EnvironmentVariables</key>
  <dict>
    <key>ROOT</key>
    <string>$ROOT</string>
  </dict>

  <key>StandardOutPath</key>
  <string>$STDOUT_LOG</string>
  <key>StandardErrorPath</key>
  <string>$STDERR_LOG</string>
</dict>
</plist>
PL

# reload
launchctl unload "$PLIST" >/dev/null 2>&1 || true
launchctl load "$PLIST"

UID="$(id -u)"
launchctl kickstart -k "gui/$UID/com.02luka.mls-symlink-guard"

echo "=== LaunchAgent status (key lines) ==="
launchctl print "gui/$UID/com.02luka.mls-symlink-guard" 2>/dev/null | grep -E "state =|runs =|last exit code =|pid =" || true

echo ""
echo "=== Tail logs ==="
tail -n 30 "$STDOUT_LOG" 2>/dev/null || true
tail -n 30 "$STDERR_LOG" 2>/dev/null || true
