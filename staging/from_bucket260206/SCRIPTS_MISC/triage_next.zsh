#!/usr/bin/env zsh
set -euo pipefail

echo "== 1) Port 7001 ownership =="
lsof -nP -iTCP:7001 -sTCP:LISTEN || true
echo

echo "== 2) Which processes mention 7001 (opal/mary) =="
ps aux | egrep "7001|opal_api_server|mary_bridge|uvicorn" | egrep -v "egrep" || true
echo

echo "== 3) Find LaunchAgents likely related to mary/opals =="
ls -1 "$HOME/Library/LaunchAgents" | egrep "02luka|opal|mary|bridge" || true
echo

echo "== 4) Check clc_worker module presence =="
BASE="$HOME/02luka"
if [[ -d "$BASE/agents" ]]; then
  ls -la "$BASE/agents" | sed -n '1,80p'
fi
echo

TARGET1="$BASE/agents/clc_local"
TARGET2="$BASE/agents/clc_local/clc_worker.py"
echo "Path check: $TARGET1"
[[ -d "$TARGET1" ]] && echo "OK: dir exists" || echo "MISSING: dir not found"
echo "File check: $TARGET2"
[[ -f "$TARGET2" ]] && echo "OK: file exists" || echo "MISSING: file not found"
echo

echo "== 5) Quick grep: which plists reference clc_worker / mary_bridge / 7001 =="
grep -R --line-number --no-messages "clc_worker" "$HOME/Library/LaunchAgents" | head -n 40 || true
grep -R --line-number --no-messages "mary_bridge" "$HOME/Library/LaunchAgents" | head -n 40 || true
grep -R --line-number --no-messages "7001" "$HOME/Library/LaunchAgents" | head -n 40 || true
echo

echo "== DONE =="
echo "Next decision:"
echo "- If mary plist references 7001: change it to a different port OR disable that bind behavior."
echo "- If clc_worker file is missing: disable its LaunchAgent (it will never heal) OR point it to the new location."
