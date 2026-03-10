#!/usr/bin/env zsh
set -euo pipefail

ts="$(date +%y%m%d_%H%M%S)"
uid="${UID}"
qdir="${HOME}/0luka/observability/quarantine/launchd/${ts}"
mkdir -p "$qdir"

labels=(
  "com.02luka.mls.ledger.monitor"
  "com.02luka.shell-watcher"
  "com.02luka.mary-dispatch"
)

# candidate plist locations (user + system)
plist_paths=()
for lbl in "${labels[@]}"; do
  plist_paths+=("${HOME}/Library/LaunchAgents/${lbl}.plist")
  plist_paths+=("/Library/LaunchAgents/${lbl}.plist")
  plist_paths+=("/Library/LaunchDaemons/${lbl}.plist")
done

echo "== Stop Bleeding (Final) =="
echo "ts: $ts"
echo "quarantine: $qdir"
echo

echo "## BEFORE: launchd presence"
for lbl in "${labels[@]}"; do
  echo "--- $lbl"
  (launchctl print "gui/${uid}/${lbl}" >/dev/null 2>&1 && echo "GUI: loaded") || echo "GUI: not loaded"
  (sudo launchctl print "system/${lbl}" >/dev/null 2>&1 && echo "SYSTEM: loaded") || echo "SYSTEM: not loaded"
done
echo

echo "## BACKUP plists (if found)"
for p in "${plist_paths[@]}"; do
  if [[ -f "$p" ]]; then
    echo "backup: $p"
    cp -av "$p" "$qdir"/
  fi
done
echo

echo "## UNLOAD / BOOTOUT (best-effort)"
for lbl in "${labels[@]}"; do
  echo "--- unloading $lbl"

  # Try user GUI domain first (modern launchctl)
  if launchctl print "gui/${uid}/${lbl}" >/dev/null 2>&1; then
    echo "bootout gui/${uid}/${lbl}"
    launchctl bootout "gui/${uid}/${lbl}" >/dev/null 2>&1 || true
  fi

  # Then system domain
  if sudo launchctl print "system/${lbl}" >/dev/null 2>&1; then
    echo "sudo bootout system/${lbl}"
    sudo launchctl bootout "system/${lbl}" >/dev/null 2>&1 || true
  fi

  # Fallback: unload via known plist path if still sticky
  for p in "${HOME}/Library/LaunchAgents/${lbl}.plist" "/Library/LaunchAgents/${lbl}.plist" "/Library/LaunchDaemons/${lbl}.plist"; do
    if [[ -f "$p" ]]; then
      echo "fallback unload plist: $p"
      if [[ "$p" == ${HOME}/Library/LaunchAgents/* ]]; then
        launchctl unload "$p" >/dev/null 2>&1 || true
      else
        sudo launchctl unload "$p" >/dev/null 2>&1 || true
      fi
    fi
  done
done
echo

echo "## AFTER: launchd presence"
for lbl in "${labels[@]}"; do
  echo "--- $lbl"
  (launchctl print "gui/${uid}/${lbl}" >/dev/null 2>&1 && echo "GUI: STILL loaded") || echo "GUI: not loaded"
  (sudo launchctl print "system/${lbl}" >/dev/null 2>&1 && echo "SYSTEM: STILL loaded") || echo "SYSTEM: not loaded"
done
echo

echo "## Quick signal check (recent restart loops)"
for f in \
  "${HOME}/02luka/logs/mary_dispatcher.log" \
  "${HOME}/02luka/logs/shell_watcher.log" \
  "${HOME}/0luka/g/logs/mls_watcher.err.log"
do
  if [[ -f "$f" ]]; then
    echo "--- tail: $f"
    tail -n 20 "$f" || true
    echo
  fi
done

echo "DONE. Plists (if any) quarantined at: $qdir"
