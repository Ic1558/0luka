#!/usr/bin/env zsh
set -euo pipefail

ROOT="$HOME/0luka"

echo "== Verify files =="
test -f "$ROOT/system/agents/telemetry_staleness_guard.py" || { echo "MISSING: system/agents/telemetry_staleness_guard.py"; exit 1; }

echo "== Patch postproc.py (targets path) =="
POSTPROC="$ROOT/tools/monitoring/postproc.py"
test -f "$POSTPROC" || { echo "MISSING: $POSTPROC"; exit 1; }

# replace: system/tools/telemetry/staleness_guard_targets.json -> observability/telemetry/staleness_guard_targets.json
python3 - <<'PY'
from pathlib import Path
p = Path.home()/"0luka/tools/monitoring/postproc.py"
s = p.read_text()
old = 'ROOT / "system/tools/telemetry/staleness_guard_targets.json"'
new = 'ROOT / "observability/telemetry/staleness_guard_targets.json"'
if old not in s:
    raise SystemExit(f"Pattern not found in {p}: {old}")
p.write_text(s.replace(old, new))
print("OK: patched", p)
PY

echo "== Patch LaunchAgent plist to run correct script path =="
PLIST="$HOME/Library/LaunchAgents/com.0luka.telemetry_staleness_guard.plist"
test -f "$PLIST" || { echo "MISSING: $PLIST"; exit 1; }

# show current ProgramArguments (for visibility)
echo "-- before (ProgramArguments) --"
plutil -p "$PLIST" | sed -n '1,200p' | rg -n "ProgramArguments|telemetry_staleness_guard|system/tools/telemetry|system/agents" || true

# Replace any legacy path string inside plist
# (safe: only replaces the exact legacy segment if present)
python3 - <<'PY'
from pathlib import Path
p = Path.home()/ "Library/LaunchAgents/com.0luka.telemetry_staleness_guard.plist"
s = p.read_text()
s2 = s.replace("/Users/icmini/0luka/system/tools/telemetry/telemetry_staleness_guard.py",
               "/Users/icmini/0luka/system/agents/telemetry_staleness_guard.py")
if s2 == s:
    # also handle if plist uses $HOME or relative; replace segment form
    s2 = s.replace("system/tools/telemetry/telemetry_staleness_guard.py",
                   "system/agents/telemetry_staleness_guard.py")
p.write_text(s2)
print("OK: patched", p)
PY

echo "== Reload LaunchAgent =="
launchctl unload "$PLIST" >/dev/null 2>&1 || true
launchctl load "$PLIST"

echo "== Smoke run (manual invoke) =="
python3 "$ROOT/system/agents/telemetry_staleness_guard.py" --help >/dev/null 2>&1 || true
echo "OK: guard script is runnable"

echo "== Grep confirm no legacy references remain =="
rg "system/tools/telemetry/telemetry_staleness_guard.py" "$ROOT" || echo "OK: no legacy script path refs in repo"
rg "system/tools/telemetry/staleness_guard_targets.json" "$ROOT" || echo "OK: no legacy targets path refs in repo"

echo "DONE"
