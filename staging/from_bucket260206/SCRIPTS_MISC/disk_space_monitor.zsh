#!/usr/bin/env zsh
set -euo pipefail

# ---- Config ----
THRESHOLD_GB="${DISK_THRESHOLD_GB:-15}"
LOG_FILE="${DISK_MONITOR_LOG:-$HOME/disk_space_monitor.log}"
CFG_FILE="${DISK_MONITOR_CFG:-$HOME/.config/02luka/disk_monitor.env}"
CANONICAL_SECRETS="$HOME/.config/02luka/secrets/telegram.env"
HOSTNAME_STR="$(scutil --get ComputerName 2>/dev/null || hostname)"
NOW="$(date '+%Y-%m-%d %H:%M:%S')"

mkdir -p "$(dirname "$CFG_FILE")"

# Load disk monitor config if present
if [[ -f "$CFG_FILE" ]]; then
  set -a; source "$CFG_FILE"; set +a
fi

# Load canonical Telegram secrets if present (takes precedence)
if [[ -f "$CANONICAL_SECRETS" ]]; then
  set -a; source "$CANONICAL_SECRETS"; set +a
fi

log() { print -r -- "[$NOW] $*" | tee -a "$LOG_FILE" >/dev/null; }

free_kb=$(df -k / | awk 'NR==2{print $4}')
used_pct=$(df -h / | awk 'NR==2{print $5}')
total_kb=$(df -k / | awk 'NR==2{print $2}')
free_gb=$(awk -v k="$free_kb" 'BEGIN{printf "%.2f", k/1048576}')
total_gb=$(awk -v k="$total_kb" 'BEGIN{printf "%.2f", k/1048576}')
snap_cnt=$(tmutil listlocalsnapshots / 2>/dev/null | wc -l | tr -d ' ')
purgeable=$(diskutil apfs listVolumeGroups 2>/dev/null | grep -i 'Purgeable' | head -n1 | awk '{print $2" "$3}' || true)

disk_status="OK"
if (( ${free_gb%.*} < THRESHOLD_GB )); then disk_status="LOW"; fi

msg=$(printf '%s — Disk Monitor\nHost: %s\nFree: %s GB (%s used)\nTotal: %s GB\nSnapshots: %s\nPurgeable: %s\nThreshold: %s GB'\
        "$(date '+%Y-%m-%d %H:%M:%S')" "$HOSTNAME_STR" "$free_gb" "$used_pct" "$total_gb" "$snap_cnt" "${purgeable:-n/a}" "$THRESHOLD_GB")

log "$disk_status :: ${msg//\n'/' | '}"

# Local notification
osascript -e "display notification \"Free: ${free_gb} GB • ${used_pct} used • Snapshots: ${snap_cnt}\" with title \"02luka Disk Monitor (${disk_status})\""

# Optional Telegram
if [[ -n "${TELEGRAM_BOT_TOKEN:-}" && -n "${TELEGRAM_CHAT_ID:-}" ]]; then
  text="[$disk_status] 02luka Disk Monitor
$HOSTNAME_STR
Free: ${free_gb} GB (${used_pct} used)
Total: ${total_gb} GB
Snapshots: ${snap_cnt}
Purgeable: ${purgeable:-n/a}
Threshold: ${THRESHOLD_GB} GB
$(date '+%Y-%m-%d %H:%M:%S')"
  curl -sS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
       -d chat_id="${TELEGRAM_CHAT_ID}" \
       --data-urlencode text="$text" >/dev/null || true
fi

# Exit non-zero only when below threshold
if [[ "$disk_status" == "LOW" ]]; then exit 2; fi
