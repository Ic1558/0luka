#!/usr/bin/env zsh
set -euo pipefail
export LC_ALL=en_US.UTF-8

PATTERN="${PATTERN:-antigravity|a2a-server\.mjs|pyrefly|codex|claude-proxy|gemini|openai|app-server}"
EXCLUDE_PATTERN="${EXCLUDE_PATTERN:-}"
SWAP_GB="${SWAP_GB:-4}"
STATE_FILE="${STATE_FILE:-$HOME/.antigravity_guard.state}"

timestamp() {
  date "+%Y-%m-%d %H:%M:%S"
}

swap_used_mb() {
  sysctl vm.swapusage | awk -F'used = ' '{print $2}' | awk -F'M' '{print $1}'
}

swap_used_gb() {
  local mb
  mb="$(swap_used_mb)"
  awk -v m="$mb" 'BEGIN {printf "%.2f", m/1024}'
}

list_matches() {
  pgrep -laf "$PATTERN" 2>/dev/null || true
}

filter_lines() {
  local line cmd
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    cmd="${line#* }"
    if [[ -n "$EXCLUDE_PATTERN" && "$cmd" =~ $EXCLUDE_PATTERN ]]; then
      continue
    fi
    echo "$line"
  done
}

launchd_label_for_pid() {
  local pid="$1"
  launchctl list 2>/dev/null | awk -v pid="$pid" '$1==pid {print $3}'
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

echo "[$(timestamp)] guard check"

swap_gb="$(swap_used_gb)"
echo "swap used: ${swap_gb} GB (threshold ${SWAP_GB} GB)"

alert_swap=0
if awk -v a="$swap_gb" -v b="$SWAP_GB" 'BEGIN {exit (a > b ? 0 : 1)}'; then
  alert_swap=1
  echo "ALERT: swap above threshold"
fi

current_raw="$(list_matches)"
current="$(printf "%s\n" "$current_raw" | filter_lines)"

tmp_prev="$(mktemp)"
tmp_cur="$(mktemp)"
trap 'rm -f "$tmp_prev" "$tmp_cur"' EXIT

printf "%s\n" "$current" | sort > "$tmp_cur"

if [[ -f "$STATE_FILE" ]]; then
  sort "$STATE_FILE" > "$tmp_prev"
  new_lines="$(comm -13 "$tmp_prev" "$tmp_cur" || true)"
else
  new_lines="$current"
fi

if [[ -n "$new_lines" ]]; then
  echo "new or respawned processes detected:"
  echo "$new_lines"
  echo ""
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    pid="${line%% *}"
    print_chain "$pid"
    label="$(launchd_label_for_pid "$pid" || true)"
    if [[ -n "$label" ]]; then
      echo "launchd label: $label"
    fi
    echo ""
  done <<< "$new_lines"
else
  echo "no new matching processes"
fi

printf "%s\n" "$current" > "$STATE_FILE"

if [[ "$alert_swap" -eq 0 && -z "$new_lines" ]]; then
  exit 0
fi
