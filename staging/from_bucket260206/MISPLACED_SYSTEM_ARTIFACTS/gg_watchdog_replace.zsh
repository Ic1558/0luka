#!/usr/bin/env zsh
set -euo pipefail
F="$HOME/02luka/tools/gg_workers_watchdog.zsh"
mkdir -p "$HOME/02luka/tools" "$HOME/02luka/logs/launchd"
[[ -f "$F" ]] && cp "$F" "${F}.bak.$(date +%s)"

cat > "$F" <<'WD'
#!/usr/bin/env zsh
set -euo pipefail

# --- Config / paths ---
SOT="${SOT:-$HOME/02luka}"
STATUS="$HOME/gg_workers_status.zsh"
LOGD="$SOT/logs/launchd"
LOGC="$SOT/logs/agents/ollama_worker/code_worker.log"
LOGN="$SOT/logs/agents/ollama_worker/nlp_worker.log"
LERRC="$LOGD/com.02luka.worker.code.err.log"
LERRN="$LOGD/com.02luka.worker.nlp.err.log"
mkdir -p "$LOGD" "$(dirname "$LOGC")"

# --- Notifications (stdout-only for now; easy to swap to Telegram later) ---
notify_fail() {
  print -r -- "$1" >> "$LOGD/com.02luka.watchdog.workers.err.log"
}

# --- Health check ---
if "$STATUS" >/dev/null 2>&1; then
  # healthy
  exit 0
fi

# --- Compose context BEFORE repair attempt (for debugging if repair fails) ---
ts=$(date '+%F %T')
host=$(hostname -s)
prectx="❌ Workers health FAIL @ ${ts} on ${host}
--- tail code.err ---
$(tail -n 10 "$LERRC" 2>/dev/null)
--- tail nlp.err ---
$(tail -n 10 "$LERRN" 2>/dev/null)
--- last code log ---
$(tail -n 5 "$LOGC" 2>/dev/null)
--- last nlp log ---
$(tail -n 5 "$LOGN" 2>/dev/null)
"

# --- AUTO-REPAIR: restart both workers ---
for L in com.02luka.worker.code com.02luka.worker.nlp; do
  launchctl bootout "gui/${UID}/${L}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/${UID}" "$HOME/Library/LaunchAgents/${L}.plist" || true
  launchctl kickstart -kp "gui/${UID}/${L}" || true
done

# give them a tiny bit of time and re-check
sleep 2
if "$STATUS" >/dev/null 2>&1; then
  printf "%s\n" "[watchdog] auto-repair succeeded @ $(date '+%F %T') on $(hostname -s)" >> "$LOGD/com.02luka.watchdog.workers.out.log"
  exit 0
fi

# --- Final failure path ---
summary="${prectx}
(After auto-repair attempt: still failing)"
notify_fail "$summary"
exit 1
WD
chmod +x "$F"

# restart watchdog LaunchAgent to pick up new file
launchctl bootout "gui/${UID}/com.02luka.watchdog.workers" >/dev/null 2>&1 || true
launchctl bootstrap "gui/${UID}" "$HOME/Library/LaunchAgents/com.02luka.watchdog.workers.plist"
launchctl kickstart -kp "gui/${UID}/com.02luka.watchdog.workers"

echo "✅ watchdog replaced + restarted"
