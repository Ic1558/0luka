#!/usr/bin/env zsh
set -euo pipefail
F="$HOME/02luka/tools/services/clc_wo_processor.cjs"
if [[ -f "$F" ]]; then
  TS=$(date +%s)
  cp -p "$F" "${F}.bak.${TS}"
  /usr/bin/python3 - "$F" <<'PY'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1])
s = p.read_text()
new = "const SOT = process.env.LUKA_HOME || '/Users/icmini/02luka';"
s2, n = re.subn(r"const\s+SOT\s*=\s*.*?;", new, s, flags=re.S)
if n == 0:
    s2 = new + "\n" + s
p.write_text(s2)
print(f"patched {p} (replacements: {n})")
PY
  echo "✅ clc_wo_processor.cjs normalized"
else
  echo "ℹ️  not found: $F (skip)"
fi
