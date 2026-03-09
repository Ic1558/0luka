#!/usr/bin/env zsh
set -euo pipefail

OLD="/Users/icmini/Documents/atg.sh"
NEW="/Users/icmini/02luka/tools/raycast_atg_snapshot.zsh"

if [[ ! -f "$OLD" ]]; then
  echo "ERR: missing: $OLD" >&2
  exit 1
fi
if [[ ! -f "$NEW" ]]; then
  echo "ERR: missing: $NEW" >&2
  exit 1
fi

# Backup once
ts="$(date +%Y%m%d_%H%M%S)"
cp -n "$OLD" "${OLD}.bak.${ts}" || true

# Overwrite OLD with a shim that delegates to NEW
cat > "$OLD" <<'SH'
#!/bin/sh
exec /Users/icmini/02luka/tools/raycast_atg_snapshot.zsh "$@"
SH

chmod +x "$OLD"

echo "OK: shim installed:"
ls -l "$OLD"
echo "OK: first lines:"
head -n 5 "$OLD"
