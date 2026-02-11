#!/usr/bin/env zsh
set -euo pipefail

LABEL="com.02luka.htmlhub"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
HTML_DIR="$HOME/02luka/html"
LOG_DIR="$HOME/Library/Logs"
OUT_LOG="$LOG_DIR/htmlhub.out.log"
ERR_LOG="$LOG_DIR/htmlhub.err.log"

mkdir -p "$HTML_DIR" "$LOG_DIR"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>${LABEL}</string>

  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/env</string>
    <string>python3</string>
    <string>-m</string>
    <string>http.server</string>
    <string>8080</string>
  </array>

  <key>WorkingDirectory</key><string>${HTML_DIR}</string>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>

  <key>StandardOutPath</key><string>${OUT_LOG}</string>
  <key>StandardErrorPath</key><string>${ERR_LOG}</string>
</dict>
</plist>
PLIST

# รีโหลดเอเจนต์อย่างปลอดภัย
if launchctl list | grep -q "$LABEL"; then
  launchctl unload "$PLIST" || true
fi
launchctl load -w "$PLIST"

# ตรวจสอบผลลัพธ์แบบเร็ว
sleep 1
echo "Listening on :8080?"
lsof -nP -iTCP:8080 -sTCP:LISTEN || true
echo "Probe:"
curl -sS -I "http://127.0.0.1:8080" | head -n1 || true

echo "Done. Logs → $OUT_LOG  /  $ERR_LOG"
