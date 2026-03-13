#!/usr/bin/env zsh
set -euo pipefail

TS_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
TS_SAFE="${TS_UTC//:/-}"
HOST_SHORT="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"
UID_NUM="$(id -u)"
REPORT_DIR="${HOME}/0luka/g/reports/mac-mini"
OUT_FILE="${REPORT_DIR}/runtime_inventory_${TS_SAFE}.md"

mkdir -p "${REPORT_DIR}"
exec > >(tee "${OUT_FILE}") 2>&1

echo "# Mac mini Runtime Inventory"
echo
echo "**Timestamp (UTC):** ${TS_UTC}  "
echo "**Host:** ${HOST_SHORT}  "
echo "**User:** ${USER:-unknown}  "
echo "**UID:** ${UID_NUM}"
echo
echo "---"
echo

echo "## 1. launchd labels"
echo '```text'
launchctl list | egrep 'antigravity|0luka|bridge|codex|gemini|mission|watchdog|qs|redis|opal' || true
echo '```'
echo

echo "## 2. launchd details"
for label in \
  com.antigravity.controltower \
  com.antigravity.hq \
  com.0luka.dispatcher \
  com.0luka.sovereign-loop \
  com.0luka.ledger-watchdog \
  com.0luka.activity-feed-maintenance \
  com.0luka.notebook_sync \
  com.0luka.rotate-logs \
  com.0luka.phase_o_daily \
  com.0luka.ram-monitor \
  com.0luka.universal-qs-api \
  com.0luka.briefing-engine \
  com.0luka.browser_op.worker \
  com.0luka.bridge_watchdog \
  com.0luka.bridge_consumer.codex \
  com.0luka.bridge_consumer.liam \
  com.0luka.bridge_consumer.lisa \
  com.0luka.session_recorder \
  com.0luka.heartbeat \
  com.0luka.atg_bridge_emit \
  com.0luka.atg_bridge_watch \
  work.0luka.executor.lisa \
  work.0luka.bridge.consumer \
  work.0luka.inbox_bridge \
  work.0luka.dashboard.briefing
do
  echo "### ${label}"
  echo '```text'
  launchctl print "gui/${UID_NUM}/${label}" 2>/dev/null || echo "not loaded"
  echo '```'
  echo
done

echo "## 3. plist files on disk"
echo '```text'
find "${HOME}/Library/LaunchAgents" /Library/LaunchAgents /Library/LaunchDaemons \
  -maxdepth 1 -type f \
  \( -iname "*0luka*" -o -iname "*antigravity*" -o -iname "*codex*" -o -iname "*gemini*" -o -iname "*bridge*" -o -iname "*watchdog*" -o -iname "*mission*" -o -iname "*redis*" -o -iname "*opal*" -o -iname "*qs*" \) \
  2>/dev/null | sort
echo '```'
echo

echo "## 4. active listening ports"
echo '```text'
lsof -nP -iTCP -sTCP:LISTEN | egrep 'COMMAND|Python|redis|ControlCe|Antigravi|Electron|Google|language_|opencode|ollama|uvicorn|codex'
echo '```'
echo

echo "## 5. key port ownership"
for port in 8089 7001 7000 5000 6379 9222; do
  echo "### port ${port}"
  echo '```text'
  lsof -nP -i :"${port}" || true
  echo '```'
  echo
done

echo "## 6. runtime processes"
echo '```text'
ps aux | egrep 'control_tower|antigravity_prod|bridge_consumer|codex app-server|a2a-server|language_server|redis|uvicorn|opencode|ollama|dispatch|sovereign|watchdog|opal_api' | grep -v egrep
echo '```'
echo

echo "## 7. process tree hints"
echo '```text'
ps -axo pid,ppid,etime,stat,command | egrep 'control_tower|antigravity_prod|Antigravity.app|codex app-server|a2a-server|language_server_macos_arm|antigravity-browser-profile|opal_api' | grep -v egrep
echo '```'
echo

echo "## 8. browser-profile residue signals"
echo '```text'
ps -axo pid,ppid,etime,command | grep "${HOME}/.gemini/antigravity-browser-profile" | grep -v grep || true
echo '```'
echo

echo "## 9. quick ownership checks"
echo '```text'
launchctl print "gui/${UID_NUM}/com.antigravity.controltower" 2>/dev/null || true
launchctl print "gui/${UID_NUM}/com.antigravity.hq" 2>/dev/null || true
lsof -nP -i :8089 || true
ps aux | grep antigravity_prod | grep -v grep || true
echo '```'
echo

echo "---"
echo
echo "Generated: ${OUT_FILE}"
