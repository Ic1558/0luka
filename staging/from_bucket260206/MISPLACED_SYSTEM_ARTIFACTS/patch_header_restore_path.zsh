#!/usr/bin/env zsh
set -euo pipefail
IFS=$'\n\t'

HDR="$HOME/0luka/skills/_shared/header_contract.zsh"
[[ -f "$HDR" ]] || { print -r -- "ERR: missing $HDR"; exit 2; }

# Insert PATH normalization if not already present.
# - Keeps existing PATH if it already includes /usr/bin
# - Otherwise prepends macOS safe defaults
python3 - <<'PY'
import re, pathlib
p = pathlib.Path.home() / "0luka/skills/_shared/header_contract.zsh"
s = p.read_text(encoding="utf-8")

marker = "# 2. Environment Resolution"
if marker not in s:
    raise SystemExit("ERR: header marker not found")

if "OLUKA_PATH_NORMALIZED" in s:
    print("OK: PATH normalization already present")
    raise SystemExit(0)

inject = r'''
# PATH normalization (macOS safe defaults). Some venv/agents can clobber PATH.
# Keep user's PATH, but ensure core tools are reachable.
if [[ -z "${OLUKA_PATH_NORMALIZED:-}" ]]; then
  export OLUKA_PATH_NORMALIZED=1
  if [[ ":${PATH}:" != *":/usr/bin:"* ]]; then
    export PATH="/usr/bin:/bin:/usr/sbin:/sbin:${PATH}"
  fi
fi

'''

s2 = s.replace(marker, marker + inject, 1)
p.write_text(s2, encoding="utf-8")
print("OK: patched", str(p))
PY

chmod +x "$HDR" || true
print -r -- "OK: header PATH patch applied: $HDR"
