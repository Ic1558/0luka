#!/usr/bin/env zsh
set -euo pipefail

REPO="$HOME/02luka"
F="$REPO/tools/atg_gc.zsh"

if [[ ! -f "$F" ]]; then
  echo "ERROR: not found: $F" >&2
  exit 1
fi

cp -n "$F" "$F.bak.$(date +%Y%m%d_%H%M%S)"

python3 - <<'PY'
import re, pathlib

p = pathlib.Path.home() / "02luka" / "tools" / "atg_gc.zsh"
s = p.read_text(encoding="utf-8")

marker = "# --- GC: orphan temp workfiles (can land in rejected/pending/etc) ---"
if marker in s:
    print("[patch-gc] already patched (marker found)")
    raise SystemExit(0)

block = r'''
# --- GC: orphan temp workfiles (can land in rejected/pending/etc) ---
# These are internal work artifacts and should never accumulate.
# We clean them across the whole ATG inbox tree, but ONLY within the inbox root.
if [[ -n "${ATG_INBOX:-}" ]] && [[ -d "$ATG_INBOX" ]]; then
  _tmp_days="${TMP_DAYS:-2}"
  find "$ATG_INBOX" -type f -name '.work_*.zsh.*' -mtime +"$_tmp_days" -print -delete 2>/dev/null || true
  rmdir "$ATG_INBOX/tmp_orphans" 2>/dev/null || true
fi
# --- /GC: orphan temp workfiles ---
'''.lstrip("\n")

# Insert right after the line that prints the banner thresholds (the line containing: pending>... rejected>... archive>... tmp>... logs>...)
m = re.search(r'^\s*echo\s+.*pending>.*rejected>.*archive>.*tmp>.*logs>.*\s*$', s, flags=re.M)
if not m:
    # Fallback: insert near top after first ATG_INBOX assignment if present
    m2 = re.search(r'^\s*ATG_INBOX\s*=.*$', s, flags=re.M)
    if not m2:
        # Last resort: insert after shebang line
        m3 = re.search(r'^#!.*\n', s)
        idx = m3.end() if m3 else 0
        s = s[:idx] + "\n" + block + "\n" + s[idx:]
    else:
        idx = m2.end()
        s = s[:idx] + "\n\n" + block + "\n" + s[idx:]
else:
    idx = m.end()
    s = s[:idx] + "\n\n" + block + "\n" + s[idx:]

p.write_text(s, encoding="utf-8")
print("[patch-gc] patched:", str(p))
PY

echo "[patch-gc] quick check:"
grep -n "orphan temp workfiles" -n "$F" || true
