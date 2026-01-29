#!/usr/bin/env zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LABEL="com.0luka.briefing-engine"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOGDIR="$ROOT/observability/retention/briefings"
mkdir -p "$LOGDIR" "$HOME/Library/LaunchAgents"

cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key><string>${LABEL}</string>

    <key>ProgramArguments</key>
    <array>
      <string>/usr/bin/env</string>
      <string>zsh</string>
      <string>${ROOT}/tools/briefing/build_briefing.zsh</string>
    </array>

    <key>RunAtLoad</key><true/>
    <key>StartInterval</key><integer>43200</integer>

    <key>StandardOutPath</key><string>${LOGDIR}/launchd_stdout.log</string>
    <key>StandardErrorPath</key><string>${LOGDIR}/launchd_stderr.log</string>
  </dict>
</plist>
PL

launchctl unload "$PLIST" >/dev/null 2>&1 || true
launchctl load "$PLIST"

echo "OK: installed + loaded LaunchAgent:"
echo " - $PLIST"
echo
echo "Run once now:"
echo " - ${ROOT}/tools/briefing/build_briefing.zsh"
