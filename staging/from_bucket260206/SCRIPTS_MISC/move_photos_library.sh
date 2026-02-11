#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ~/move_photos_library.sh "/Volumes/<SSD_NAME>" "/Users/<you>/Pictures/Photos Library.photoslibrary" [--cleanup]

TARGET_VOL="${1:-}"
SRC_LIB="${2:-}"
CLEANUP="${3:-}"

if [[ -z "${TARGET_VOL}" || -z "${SRC_LIB}" ]]; then
  echo "Usage: $0 \"/Volumes/<SSD_NAME>\" \"/Users/<you>/Pictures/Photos Library.photoslibrary\" [--cleanup]"
  exit 1
fi

# 0) Quit Photos if running
if pgrep -x "Photos" >/dev/null 2>&1; then
  echo "⚠️  Photos is running → quitting…"
  osascript -e 'tell application "Photos" to quit'
  sleep 2
fi
if pgrep -x "Photos" >/dev/null 2>&1; then
  echo "❌ Photos did not quit. Close it and re-run."
  exit 2
fi

# 1) Existence checks
[[ -d "$TARGET_VOL" ]] || { echo "❌ Target volume not found: $TARGET_VOL"; exit 3; }
[[ -e "$SRC_LIB" ]]    || { echo "❌ Source library not found: $SRC_LIB"; exit 4; }

LIB_NAME="$(basename "$SRC_LIB")"
DST_LIB="$TARGET_VOL/$LIB_NAME"

# 2) Space check (need library size + ~2GB buffer)
echo "ℹ️ Checking sizes…"
LIB_SIZE_BYTES=$(du -sk "$SRC_LIB" | awk '{print $1*1024}')
AVAIL_BYTES=$(df -k "$TARGET_VOL" | tail -1 | awk '{print $4*1024}')
echo "   Library: $((LIB_SIZE_BYTES/1024/1024)) MB"
echo "   Target free: $((AVAIL_BYTES/1024/1024)) MB"
(( AVAIL_BYTES > LIB_SIZE_BYTES + 2*1024*1024*1024 )) || { echo "❌ Not enough free space on target."; exit 5; }

# 3) Try to enable “Ignore ownership…” (best-effort; requires sudo)
if command -v vsdbutil >/dev/null 2>&1; then
  echo "🔧 Enabling 'Ignore ownership on this volume' (best-effort)…"
  sudo vsdbutil -a "$TARGET_VOL" || true
fi

# 4) Avoid overwrite
if [[ -e "$DST_LIB" ]]; then
  TS=$(date +%Y%m%d_%H%M%S)
  DST_LIB="$TARGET_VOL/${LIB_NAME%.photoslibrary}_COPY_${TS}.photoslibrary"
  echo "⚠️ Destination exists; writing to: $DST_LIB"
fi

# 5) Copy safely with ditto (preserve bundle + metadata)
echo "🚚 Copying library… (this can take a while)"
ditto -V --keepParent --rsrc --extattr "$SRC_LIB" "$DST_LIB"
echo "✅ Copy complete → $DST_LIB"

# 6) Open Photos with the new library
echo "🔓 Opening Photos with the new library…"
open -a "Photos" "$DST_LIB"

cat <<'NOTE'
➡️ In Photos: Preferences (⌘, ) → General → click “Use as System Photo Library”.
   (iCloud Photos will resume against the SSD copy.)
   Verify your albums/edits. When “Up to Date”, you may clean up the original.

NOTE

# 7) Optional cleanup to Trash after confirmation
if [[ "${CLEANUP:-}" == "--cleanup" ]]; then
  echo "🗑️  --cleanup specified → moving original to Trash…"
  if pgrep -x "Photos" >/dev/null 2>&1; then
    osascript -e 'tell application "Photos" to quit'
    sleep 2
  fi
  osascript <<EOF
tell application "Finder"
  move POSIX file "$(python3 - <<'PY'
import os,sys
print(os.path.abspath(sys.argv[1]))
PY
"$SRC_LIB")" to trash
end tell
EOF
  echo "✅ Original moved to Trash. Empty Trash after final confirmation."
else
  echo "🛑 Original kept at: $SRC_LIB (safe). Re-run with --cleanup after you verify."
fi

echo "🎉 Done."
