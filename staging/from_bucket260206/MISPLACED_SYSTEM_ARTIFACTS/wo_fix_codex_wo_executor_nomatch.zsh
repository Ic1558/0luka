#!/usr/bin/env zsh
set -euo pipefail

label="com.02luka.wo_executor.codex"
uid="$(id -u)"
agents_dir="$HOME/Library/LaunchAgents"

echo "== Find plist for: $label =="

plist="$(/usr/bin/grep -rl -- "$label" "$agents_dir" 2>/dev/null | head -n 1 || true)"
if [[ -z "${plist:-}" || ! -f "$plist" ]]; then
  echo "SKIP: plist not found for $label (maybe already disabled or stored elsewhere)"
  exit 0
fi

echo "plist: $plist"
echo "== Patch plist ProgramArguments to disable zsh nomatch =="

# backup
cp -a "$plist" "$plist.bak.$(date +%Y%m%d_%H%M%S)"

# Patch strategy:
# - If ProgramArguments contains "zsh" and "-c", inject "-o" "no_nomatch" right after zsh
# - Otherwise do nothing (manual review needed)
python3 - "$plist" <<'PY'
import plistlib, sys, pathlib, re
plist_path = pathlib.Path(sys.argv[1])
data = plistlib.loads(plist_path.read_bytes())

pa = data.get("ProgramArguments")
if not isinstance(pa, list) or len(pa) < 1:
    print("NOCHANGE: ProgramArguments missing/invalid")
    sys.exit(0)

# locate zsh
try:
    i = pa.index("zsh")
except ValueError:
    # also handle /bin/zsh or /usr/bin/env zsh patterns
    i = None
    for idx, v in enumerate(pa):
        if isinstance(v, str) and v.endswith("/zsh"):
            i = idx
            break

if i is None:
    print("NOCHANGE: zsh not found in ProgramArguments")
    sys.exit(0)

# inject -o no_nomatch if not present
needle = ["-o", "no_nomatch"]
already = False
for j in range(len(pa)-1):
    if pa[j] == "-o" and pa[j+1] == "no_nomatch":
        already = True
        break

if already:
    print("NOCHANGE: already has -o no_nomatch")
    sys.exit(0)

pa[i+1:i+1] = needle
data["ProgramArguments"] = pa
plist_path.write_bytes(plistlib.dumps(data))
print("PATCHED: inserted -o no_nomatch")
PY

echo "== Reload agent =="
launchctl bootout "gui/$uid" "$plist" 2>/dev/null || true
launchctl bootstrap "gui/$uid" "$plist"

echo "== Verify no more codex WO glob errors (tail) =="
logfile="$HOME/02luka/logs/codex_wo_executor.err.log"
if [[ -f "$logfile" ]]; then
  tail -n 20 "$logfile" || true
else
  echo "log not found: $logfile"
fi
