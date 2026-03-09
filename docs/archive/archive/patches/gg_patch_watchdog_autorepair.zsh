#!/usr/bin/env zsh
set -euo pipefail
F="$HOME/02luka/tools/gg_workers_watchdog.zsh"
[[ -f "$F" ]] || { echo "not found: $F" >&2; exit 1; }
cp "$F" "${F}.bak.$(date +%s)"

python3 - "$F" <<'PY'
import sys,re
p=sys.argv[1]
s=open(p).read()
pat=r'(notify_fail\s*\(\s*\$summary\s*\)\s*\n\s*exit\s+1)'
if not re.search(pat,s,flags=re.M):
    print("Could not find failure notify block in watchdog; aborting.", file=sys.stderr)
    sys.exit(1)

insert = r'''# === AUTO-REPAIR: try restart before notifying ===
for L in com.02luka.worker.code com.02luka.worker.nlp; do
  launchctl bootout "gui/${UID}/${L}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/${UID}" "$HOME/Library/LaunchAgents/${L}.plist" || true
  launchctl kickstart -kp "gui/${UID}/${L}" || true
done
sleep 2
if "$STATUS" >/dev/null 2>&1; then
  printf "%s\n" "[watchdog] auto-repair succeeded @ $(date '+%F %T') on $(hostname -s)" >> "$HOME/02luka/logs/launchd/com.02luka.watchdog.workers.out.log"
  exit 0
fi
'''
s=re.sub(pat, insert + r'\n\1', s, count=1, flags=re.M)
open(p,'w').write(s)
PY
