#!/usr/bin/env zsh
set -e

echo "== Disabling 02luka Legacy Jobs =="
LAUNCH_AGENTS="$HOME/Library/LaunchAgents"
UID="$(id -u)"

labels=$(
  launchctl print "gui/$UID" 2>/dev/null \
    | grep -Eo '((com|org)\.02luka\.[A-Za-z0-9._-]+)' \
    | sort -u
)

if [[ -z "$labels" ]]; then
  echo "No com.02luka/org.02luka labels loaded."
  exit 0
fi

for label in $labels; do
  echo "Disabling $label ..."
  launchctl disable "gui/$UID/$label" 2>/dev/null || true

  plist="$LAUNCH_AGENTS/$label.plist"
  if [[ -f "$plist" ]]; then
    echo "Booting out $plist ..."
    launchctl bootout "gui/$UID" "$plist" 2>/dev/null || true
  fi
done

echo "== 02luka Decommissioning Step Complete =="
