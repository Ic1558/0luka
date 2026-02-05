#!/usr/bin/env zsh
set -euo pipefail
export LC_ALL=en_US.UTF-8

PATTERN="${PATTERN:-antigravity|a2a-server\.mjs|pyrefly|codex|claude-proxy|gemini|openai|app-server}"
EXCLUDE_PATTERN="${EXCLUDE_PATTERN:-}"
GRACE_SECS="${GRACE_SECS:-15}"
KILL_SECS="${KILL_SECS:-5}"
TOP_N="${TOP_N:-15}"
DRY_RUN="${DRY_RUN:-0}"

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

report_swap() {
  echo "[$(timestamp)] swap usage"
  sysctl vm.swapusage
  echo ""
}

report_top() {
  echo "[$(timestamp)] top memory (rss KB)"
  ps -axo pid,ppid,rss,etime,pcpu,comm | sort -nr -k3 | head -n "$TOP_N"
  echo ""
}

list_matches() {
  pgrep -laf "$PATTERN" 2>/dev/null || true
}

filter_matches() {
  local line pid cmd
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    pid="${line%% *}"
    cmd="${line#* }"
    if [[ -n "$EXCLUDE_PATTERN" && "$cmd" =~ $EXCLUDE_PATTERN ]]; then
      continue
    fi
    echo "$pid"
  done
}

print_chain() {
  local pid="$1"
  local cur="$pid"
  echo "process chain for pid $pid:"
  while [[ -n "$cur" && "$cur" -ne 1 ]]; do
    ps -o pid=,ppid=,command= -p "$cur" 2>/dev/null || break
    cur="$(ps -o ppid= -p "$cur" 2>/dev/null | tr -d ' ')"
  done
  if [[ "$cur" == "1" ]]; then
    ps -o pid=,ppid=,command= -p 1
  fi
}

launchd_label_for_pid() {
  local pid="$1"
  launchctl list 2>/dev/null | awk -v pid="$pid" '$1==pid {print $3}'
}

echo "== BEFORE =="
report_swap
report_top

echo "== MATCHES =="
list_matches

osascript -e 'tell application "Antigravity" to quit' >/dev/null 2>&1 || true

pids=($(list_matches | filter_matches))
if [[ ${#pids[@]} -eq 0 ]]; then
  echo "no matching processes"
  exit 0
fi

echo ""
echo "== DETAILS =="
for pid in "${pids[@]}"; do
  print_chain "$pid"
  label="$(launchd_label_for_pid "$pid" || true)"
  if [[ -n "$label" ]]; then
    echo "launchd label: $label"
  fi
  echo ""
done

if [[ "$DRY_RUN" == "1" ]]; then
  echo "DRY_RUN=1 set, not stopping processes."
  exit 0
fi

echo "== TERM =="
for pid in "${pids[@]}"; do
  kill -TERM "$pid" 2>/dev/null || true
done

sleep "$GRACE_SECS"

alive=($(list_matches | filter_matches))
if [[ ${#alive[@]} -gt 0 ]]; then
  echo "== KILL =="
  for pid in "${alive[@]}"; do
    kill -KILL "$pid" 2>/dev/null || true
  done
  sleep "$KILL_SECS"
fi

echo "== AFTER =="
report_swap
report_top

echo "== REMAINING =="
list_matches
