#!/usr/bin/env zsh
set -euo pipefail

# 1) locate repo root relative to this script if possible; otherwise use current dir
# You can run this script from repo root, or it will still print paths.
echo "=== TIME ==="
date

echo "\n=== WHOAMI / HOST ==="
whoami
hostname

echo "\n=== LAUNCHAGENT LIST ==="
launchctl list | egrep -i 'com\.02luka\.fs_watcher|fs_watcher' || true

echo "\n=== LAUNCHAGENT PRINT (user GUI domain) ==="
UID_NOW="$(id -u)"
launchctl print "gui/${UID_NOW}/com.02luka.fs_watcher" 2>/dev/null | sed -n '1,200p' || echo "launchctl print failed (maybe not in gui domain)"

echo "\n=== PLIST (first 220 lines) ==="
# try common locations
for p in \
  "$HOME/Library/LaunchAgents/com.02luka.fs_watcher.plist" \
  "/Library/LaunchAgents/com.02luka.fs_watcher.plist"
do
  if [[ -f "$p" ]]; then
    echo "--- $p ---"
    plutil -p "$p" | sed -n '1,220p'
  fi
done

echo "\n=== PROCESS CHECK ==="
pgrep -fl "fs_watcher.py|fs_watcher_launcher.sh|FS_DAEMON|ATG_RUNNER_PASSIVE" || true

echo "\n=== PYTHON PATH USED BY PROCESS (best effort) ==="
PID="$(pgrep -f "fs_watcher.py" | head -n 1 || true)"
if [[ -n "${PID:-}" ]]; then
  ps -p "$PID" -o pid,ppid,command
  lsof -p "$PID" 2>/dev/null | egrep -i 'fs_index\.jsonl|fs_watcher\.py|fs_watcher_launcher\.sh' || true
fi

echo "\n=== LOG TAIL ==="
for f in /tmp/com.02luka.fs_watcher.stdout.log /tmp/com.02luka.fs_watcher.stderr.log; do
  if [[ -f "$f" ]]; then
    echo "--- tail $f ---"
    tail -n 120 "$f"
  else
    echo "--- missing $f ---"
  fi
done

echo "\n=== TELEMETRY LOOP PROOF ==="
# show last events + specifically show any self-reference
if [[ -f "g/telemetry/fs_index.jsonl" ]]; then
  echo "--- tail telemetry ---"
  tail -n 120 g/telemetry/fs_index.jsonl
  echo "\n--- grep self-reference (should be EMPTY) ---"
  grep -n '"file":"g/telemetry/fs_index.jsonl"' g/telemetry/fs_index.jsonl || true
  echo "\n--- grep old lane (should be EMPTY if only FS_DAEMON exists) ---"
  grep -n '"lane":"ATG_RUNNER_PASSIVE"' g/telemetry/fs_index.jsonl || true
else
  echo "telemetry file not found at ./g/telemetry/fs_index.jsonl (run this script from repo root)"
fi

echo "\n=== SHOW WATCHER CONFIG SNIPPET (fs_watcher.py) ==="
# best effort: common location tools/fs_watcher.py
if [[ -f "tools/fs_watcher.py" ]]; then
  python3 - <<'PY'
from pathlib import Path
p = Path("tools/fs_watcher.py")
t = p.read_text(encoding="utf-8", errors="replace").splitlines()
# print key sections only
keys = ["ALLOWED_ROOTS", "IGNORE_EXACT", "TELEMETRY_FILE", "should_ignore", "LANE"]
for i,line in enumerate(t,1):
    if any(k in line for k in keys):
        start=max(1,i-2); end=min(len(t), i+25)
        print(f"\n--- around line {i} ---")
        for j in range(start,end+1):
            print(f"{j:04d}: {t[j-1]}")
PY
else
  echo "tools/fs_watcher.py not found (run this script from repo root)"
fi
