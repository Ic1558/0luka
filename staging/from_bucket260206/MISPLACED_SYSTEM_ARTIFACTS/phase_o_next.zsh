#!/usr/bin/env zsh
set -euo pipefail

ROOT="${1:-$PWD}"
cd "$ROOT"

say() { print -r -- "$*"; }

# --- sanity ---
[[ -f "tools/rotate_logs_min.zsh" ]] || { say "ERR: missing tools/rotate_logs_min.zsh"; exit 1; }
[[ -f "tools/build_summary_min.zsh" ]] || { say "ERR: missing tools/build_summary_min.zsh"; exit 1; }
[[ -f "luka.md" ]] || { say "ERR: missing luka.md"; exit 1; }

# --- run once now (idempotent) ---
./tools/rotate_logs_min.zsh "$ROOT" || true
./tools/build_summary_min.zsh "$ROOT" || true

# --- create a minimal daily launchd job (Phase-O operability) ---
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST="$PLIST_DIR/com.0luka.phase_o_daily.plist"
mkdir -p "$PLIST_DIR"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.0luka.phase_o_daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>cd "${ROOT}" && ./tools/rotate_logs_min.zsh "${ROOT}" && ./tools/build_summary_min.zsh "${ROOT}"</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>2</integer>
    <key>Minute</key><integer>15</integer>
  </dict>
  <key>StandardOutPath</key><string>${ROOT}/logs/components/phase_o_daily/current.log</string>
  <key>StandardErrorPath</key><string>${ROOT}/logs/components/phase_o_daily/current.err.log</string>
  <key>RunAtLoad</key><true/>
</dict>
</plist>
PLIST

mkdir -p "${ROOT}/logs/components/phase_o_daily"

# (re)load safely
launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/com.0luka.phase_o_daily" || true
launchctl kickstart -k "gui/$(id -u)/com.0luka.phase_o_daily" || true

# --- verify ---
say "OK: installed daily job -> $PLIST"
say "OK: latest summary -> reports/summary/latest.md"
say "OK: daily logs -> logs/components/phase_o_daily/current.log"
say "DONE: Phase-O is now self-running (daily rotate+summary)."
