#!/usr/bin/env zsh
LOG="$HOME/Library/Application Support/Google/DriveFS/Logs/drive_fs.txt"
DIR="$HOME/My Drive/02luka"
int=${1:-30}

echo "Watching Mirror…  (dir: $DIR)  (log: $LOG)  every ${int}s"
echo "Stop: Ctrl+C"
while true; do
  echo "=== $(date '+%F %T') ==="
  du -sh "$DIR" 2>/dev/null || echo "(dir not ready yet)"
  echo "-- recent log --"
  tail -n 20 "$LOG" 2>/dev/null | grep -E "Mirror|download|Download|Sync|Materializ|Queued|Fetched" | tail -n 10 || true
  echo
  sleep $int
done
