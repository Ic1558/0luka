#!/usr/bin/env zsh
set -euo pipefail

ts="$(date +%y%m%d_%H%M%S)"
BASE="$HOME/02luka"
QDIR="$BASE/observability/quarantine/launchd/$ts"
mkdir -p "$QDIR"

echo "== Stop Bleeding (02luka lane) =="
echo "TS: $ts"
echo "Quarantine: $QDIR"
echo

# Labels we believe are looping (from your snapshot evidence)
typeset -a TARGET_LABELS=(
  "com.02luka.mary-dispatch"
  "com.02luka.shell-watcher"
)

# Also catch likely variants / ghosts (safe: we only act if plist exists)
typeset -a GREP_HINTS=(
  "mary"
  "shell_watcher"
  "shell-watcher"
  "mary_dispatcher"
  "mary-dispatch"
)

# Paths to search (user + system)
typeset -a SEARCH_DIRS=(
  "$HOME/Library/LaunchAgents"
  "/Library/LaunchAgents"
  "/Library/LaunchDaemons"
)

echo "== 1) Snapshot current launchctl state (before) =="
{
  echo "### launchctl print gui/$(id -u) (filtered)"
  launchctl print "gui/$(id -u)" 2>/dev/null | egrep -i 'com\.02luka\.(mary|shell)|mary_dispatcher|shell_watcher|shell-watcher|mary-dispatch' || true
  echo
  echo "### launchctl list (filtered)"
  launchctl list 2>/dev/null | egrep -i 'com\.02luka\.(mary|shell)|mary_dispatcher|shell_watcher|shell-watcher|mary-dispatch' || true
} > "$QDIR/launchctl_before.txt" || true
echo "Saved: $QDIR/launchctl_before.txt"
echo

echo "== 2) Find candidate plists on disk =="
typeset -a FOUND_PLISTS=()
for d in "${SEARCH_DIRS[@]}"; do
  [[ -d "$d" ]] || continue
  for h in "${GREP_HINTS[@]}"; do
    while IFS= read -r p; do
      [[ -f "$p" ]] && FOUND_PLISTS+=("$p")
    done < <(ls -1 "$d"/*.plist 2>/dev/null | egrep -i "$h" || true)
  done
done

# De-dup
FOUND_PLISTS=("${(@u)FOUND_PLISTS[@]}")

if (( ${#FOUND_PLISTS[@]} == 0 )); then
  echo "No candidate plists found in standard locations."
else
  printf "%s\n" "${FOUND_PLISTS[@]}" | tee "$QDIR/plists_found.txt"
  echo "Saved: $QDIR/plists_found.txt"
fi
echo

echo "== 3) Attempt unload/disable by label (best-effort) =="
# We do best-effort: unload + disable in both gui and system domains
for lbl in "${TARGET_LABELS[@]}"; do
  echo "-- label: $lbl"
  # user domain
  launchctl bootout "gui/$(id -u)/$lbl" 2>/dev/null || true
  launchctl disable "gui/$(id -u)/$lbl" 2>/dev/null || true
  # system domain
  sudo -n launchctl bootout "system/$lbl" 2>/dev/null || true
  sudo -n launchctl disable "system/$lbl" 2>/dev/null || true
done
echo

echo "== 4) If we found plists: bootout by path + quarantine move =="
if (( ${#FOUND_PLISTS[@]} > 0 )); then
  for p in "${FOUND_PLISTS[@]}"; do
    echo "-- plist: $p"
    # bootout by path (works even if label differs)
    if [[ "$p" == "$HOME/"* ]]; then
      launchctl bootout "gui/$(id -u)" "$p" 2>/dev/null || true
      launchctl disable "gui/$(id -u)/$(/usr/libexec/PlistBuddy -c 'Print :Label' "$p" 2>/dev/null || echo 'unknown.label')" 2>/dev/null || true
    else
      sudo -n launchctl bootout system "$p" 2>/dev/null || true
      sudo -n launchctl disable "system/$(/usr/libexec/PlistBuddy -c 'Print :Label' "$p" 2>/dev/null || echo 'unknown.label')" 2>/dev/null || true
    fi

    # quarantine (move, not delete)
    bn="$(basename "$p")"
    dest="$QDIR/$bn"
    if [[ "$p" == "$HOME/"* ]]; then
      mv -v "$p" "$dest"
    else
      sudo -n mv -v "$p" "$dest"
      sudo -n chown "$(id -un)":"$(id -gn)" "$dest" 2>/dev/null || true
    fi
  done
fi
echo

echo "== 5) Proof (after) =="
{
  echo "### launchctl print gui/$(id -u) (filtered)"
  launchctl print "gui/$(id -u)" 2>/dev/null | egrep -i 'com\.02luka\.(mary|shell)|mary_dispatcher|shell_watcher|shell-watcher|mary-dispatch' || true
  echo
  echo "### launchctl list (filtered)"
  launchctl list 2>/dev/null | egrep -i 'com\.02luka\.(mary|shell)|mary_dispatcher|shell_watcher|shell-watcher|mary-dispatch' || true
  echo
  echo "### quarantined files"
  ls -la "$QDIR" || true
} > "$QDIR/launchctl_after.txt" || true

echo "Saved: $QDIR/launchctl_after.txt"
echo
echo "DONE. If loops persist, the culprit is likely a non-launchd supervisor (e.g. a cron, a parent daemon, or a custom watchdog) spawning them."
echo "Next: grep for 'start mary_dispatcher' writer or find the parent PID using 'ps -ef | egrep -i \"mary_dispatcher|shell_watcher\"'."
