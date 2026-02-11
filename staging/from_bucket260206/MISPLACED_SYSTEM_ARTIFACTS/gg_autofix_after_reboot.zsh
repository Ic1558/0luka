#!/usr/bin/env zsh
set -euo pipefail

UID="$(id -u)"
SOT="$HOME/02luka"
LA_DIR="$HOME/Library/LaunchAgents"
REPORT_DIR="$SOT/reports"
TS="$(date +%Y%m%d_%H%M%S)"
RPT="$REPORT_DIR/autofix_${TS}.txt"
mkdir -p "$REPORT_DIR"

log(){ print -r -- "$@" | tee -a "$RPT"; }

log "== GG Autofix After Reboot = $(date)"
log "SOT  : $SOT"
log "LA   : $LA_DIR"
log "RPT  : $RPT"
log ""

# 1) Patch LaunchAgents that still point to LocalProjects → 02luka
log "-- Patch LaunchAgents paths --"
badges=()
for P in "$LA_DIR"/com.02luka.*.plist(N); do
  if [[ -f "$P" ]]; then
    # backup once per run
    [[ -f "${P}.bak" ]] || cp -p "$P" "${P}.bak"
    before="$(grep -c '/LocalProjects/02luka_local_g/g' "$P" || true)"
    if (( before > 0 )); then
      /usr/bin/perl -0777 -pe 's|/Users/icmini/LocalProjects/02luka_local_g/g|/Users/icmini/02luka|g' -i "$P"
      log "🔧 patched: ${(t)P}"
    fi
  fi
done
log ""

# 2) Decide which labels to skip (legacy-bound) to avoid crash-loop
#    เราข้ามเฉพาะที่ยังชี้ไฟล์ใน 02luka_legacy
skip_labels=()
for P in "$LA_DIR"/com.02luka.*.plist(N); do
  [[ -f "$P" ]] || continue
  if grep -q '/02luka_legacy/' "$P"; then
    b="${P:t:r}"
    skip_labels+=("$b")
    log "⏭️  skip (legacy path): $b"
  fi
done
log ""

# 3) Bootstrap + kickstart the rest
log "-- Relaunch labels --"
for P in "$LA_DIR"/com.02luka.*.plist(N); do
  L="${P:t:r}"
  # skip legacy-bound ones
  if (( ${#skip_labels[@]} )); then
    if [[ " ${skip_labels[@]} " == *" $L "* ]]; then
      continue
    fi
  fi
  launchctl bootout "gui/${UID}/${L}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/${UID}" "$P" || true
  launchctl kickstart -kp "gui/${UID}/${L}" || true
done
log ""

# 4) Ensure Google Drive running (best-effort)
log "-- Google Drive --"
if ! pgrep -f "Google Drive" >/dev/null 2>&1; then
  open -gj -a "Google Drive" || true
  log "▶️  starting Google Drive..."
  sleep 5
fi
CLOUD="$HOME/Library/CloudStorage"
GD="$(ls -d "$CLOUD"/GoogleDrive* 2>/dev/null | head -n1 || true)"
if [[ -n "${GD:-}" ]]; then
  log "✅ Drive mount: $GD"
else
  log "⚠️  Drive mount not detected yet"
fi
log ""

# 5) Quick state + tips
log "-- LaunchAgents state --"
for P in "$LA_DIR"/com.02luka.*.plist(N); do
  L="${P:t:r}"
  if launchctl print "gui/${UID}/${L}" 2>/dev/null | grep -q "state = running"; then
    log "🟢 $L running"
  else
    log "🔴 $L not running"
    log "    launchctl bootstrap gui/${UID} \"$P\" || true"
    log "    launchctl kickstart -kp gui/${UID}/${L} || true"
  fi
done

log ""
log "== DONE :: $RPT =="
print -r -- "$RPT"
