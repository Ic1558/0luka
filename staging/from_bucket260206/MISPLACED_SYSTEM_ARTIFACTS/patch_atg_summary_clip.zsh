#!/usr/bin/env zsh
set -euo pipefail

ROOT="$HOME/02luka"
F="$ROOT/raycast/atg-snapshot-summary.command"

[[ -f "$F" ]] || { echo "missing: $F"; exit 1; }

python3 - <<'PY'
import re, pathlib
p = pathlib.Path.home() / "02luka" / "raycast" / "atg-snapshot-summary.command"
s = p.read_text(encoding="utf-8")

# 1) Ensure full silence hardening (stdin+stdout+stderr)
s = re.sub(r'(?m)^exec\s+.*$', "exec </dev/null >/dev/null 2>&1", s)

# If no exec line exists, insert after set -euo pipefail
if "exec </dev/null >/dev/null 2>&1" not in s:
    s = re.sub(r'(?m)^(set -euo pipefail\s*)$',
               r'\1\n\n# Hardening: Guarantee complete silence (Raycast stdout/stderr overwrites clipboard)\nexec </dev/null >/dev/null 2>&1\n',
               s, count=1)

# 2) Add markers + replace pbcopy section with osascript + markers.
# Replace the final clipboard block (pbcopy < ...) with a deterministic block.
pattern = r'(?s)# Copy summary to clipboard.*?\nexit 0\s*\Z'
replacement = r'''# Copy summary to clipboard (deterministic markers)
LOG="/tmp/atg_summary_clip.log"
DONE="/tmp/atg_summary_done.txt"
{
  echo "start $(date -Is 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S%z')"
  echo "script=$0"
  echo "pwd=$(pwd)"
} > "$LOG"

if [[ -f "g/core_history/latest.md" ]]; then
  osascript -e 'set the clipboard to (read (POSIX file "'"$ROOT"'/g/core_history/latest.md") as «class utf8»)' >/dev/null 2>&1 || true
else
  osascript -e 'set the clipboard to (read (POSIX file "'"$out"'") as «class utf8»)' >/dev/null 2>&1 || true
fi

echo "done $(date -Is 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S%z')" >> "$LOG"
echo "ok $(date -Is 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S%z')" > "$DONE"

exit 0
'''
if re.search(pattern, s):
    s = re.sub(pattern, replacement, s)
else:
    # If pattern didn't match, append safely at end (still deterministic)
    s = s.rstrip() + "\n\n" + replacement + "\n"

p.write_text(s, encoding="utf-8")
print("patched:", p)
PY

echo "---- verify markers ----"
rg -n "atg_summary_clip|atg_summary_done|osascript -e 'set the clipboard'" "$F" || true
