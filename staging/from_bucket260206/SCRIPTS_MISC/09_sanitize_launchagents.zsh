#!/usr/bin/env zsh
set -euo pipefail
L="$HOME/Library/LaunchAgents"
ARCH="$L/_disabled_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$ARCH"

# ย้ายไฟล์สำรอง/ปิดการใช้งานออกไป
find "$L" -maxdepth 1 -type f \( -name "*.bak*" -o -name "*.disabled" \) -print -exec mv {} "$ARCH"/ \;

echo "== Validating Program paths =="
# ตรวจ .plist จริง ๆ เท่านั้น
PLISTS=($(find "$L" -maxdepth 1 -type f -name "*.plist" | sort))
for p in "${PLISTS[@]}"; do
  PROG=$(/usr/libexec/PlistBuddy -c 'Print :ProgramArguments:0' "$p" 2>/dev/null || true)
  [[ -n "$PROG" && -x "$PROG" ]] || { echo "❌ $p -> missing/exec Program: $PROG"; continue; }
  echo "OK  $p -> $PROG"
done

echo "== Reload clean plists =="
for p in "${PLISTS[@]}"; do
  launchctl unload -w "$p" 2>/dev/null || true
  launchctl load   -w "$p" || true
  LABEL=$(/usr/libexec/PlistBuddy -c 'Print :Label' "$p" 2>/dev/null || basename "$p" .plist)
  launchctl kickstart gui/"$(id -u)"/"$LABEL" 2>/dev/null || true
  echo "✔ $LABEL reloaded"
done

echo "✅ Done. Moved backups to: $ARCH"
