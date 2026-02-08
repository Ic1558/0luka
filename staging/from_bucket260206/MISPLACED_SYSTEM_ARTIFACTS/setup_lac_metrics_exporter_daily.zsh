#!/usr/bin/env zsh
set -euo pipefail

ROOT="${LUKA_SOT:-${LUKA_ROOT:-$HOME/02luka}}"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_ID="com.02luka.lac-metrics-exporter.daily"
PLIST_PATH="$PLIST_DIR/${PLIST_ID}.plist"
LOG_DIR="$ROOT/logs"
STDOUT_LOG="$LOG_DIR/lac_metrics_exporter.stdout.log"
STDERR_LOG="$LOG_DIR/lac_metrics_exporter.stderr.log"

mkdir -p "$PLIST_DIR" "$LOG_DIR"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key><string>${PLIST_ID}</string>

    <key>ProgramArguments</key>
    <array>
      <string>/usr/bin/python3</string>
      <string>${ROOT}/tools/telemetry/lac_metrics_exporter.py</string>
      <string>--root</string><string>${ROOT}</string>
      <string>--since</string><string>24h</string>
      <string>--limit</string><string>50</string>
    </array>

    <key>StartCalendarInterval</key>
    <dict>
      <key>Hour</key><integer>8</integer>
      <key>Minute</key><integer>30</integer>
    </dict>

    <key>RunAtLoad</key><true/>
    <key>StandardOutPath</key><string>${STDOUT_LOG}</string>
    <key>StandardErrorPath</key><string>${STDERR_LOG}</string>
  </dict>
</plist>
PLIST

launchctl unload "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl load "$PLIST_PATH"

echo "Loaded LaunchAgent: $PLIST_ID"
echo "Run a one-shot now to verify output:"
/usr/bin/python3 "${ROOT}/tools/telemetry/lac_metrics_exporter.py" --root "$ROOT" --since 24h --limit 20

echo ""
echo "Outputs (symlink dir expected):"
ls -la "$ROOT/g/telemetry" | grep -E "lac_metrics_summary_latest\.(json|md)" || true

echo ""
echo "Tail logs:"
tail -50 "$STDOUT_LOG" 2>/dev/null || true
tail -50 "$STDERR_LOG" 2>/dev/null || true
