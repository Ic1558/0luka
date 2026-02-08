#!/usr/bin/env zsh
set -euo pipefail

TARGET="$HOME/0luka/interface/frontends/raycast/atg_multi_snap.zsh"
TS="$(date +"%y%m%d_%H%M%S")"
BAK="${TARGET}.bak.${TS}"
TMP="$(mktemp -t atg_multi_snap.zsh.XXXXXX)"

[[ -f "$TARGET" ]] || { echo "ERROR: missing $TARGET" >&2; exit 1; }

cp -p "$TARGET" "$BAK"
echo "Backup: $BAK"

python3 - <<'PY'
import re, sys, pathlib

path = pathlib.Path.home() / "0luka/interface/frontends/raycast/atg_multi_snap.zsh"
s = path.read_text(encoding="utf-8")

old_changes = r'''echo "$st" | grep -v '^\?\?' | head -n "$D_CHANGED" || echo "(none)"'''
new_changes = r'''echo "$st" | grep -E '^[ MADRC][MADRC]' | head -n "$D_CHANGED" || echo "(none)"'''

old_untracked = r'''echo "$st" | grep '^\?\?' | head -n "$D_UNTRACKED" || echo "(none)"'''
new_untracked = r'''echo "$st" | grep '^\?\?' | head -n "$D_UNTRACKED" || echo "(none)"'''

need = [old_changes, old_untracked]
missing = [x for x in need if x not in s]
if missing:
    print("ERROR: expected patterns not found; refusing to patch.", file=sys.stderr)
    for m in missing:
        print("Missing:", m, file=sys.stderr)
    sys.exit(2)

s2 = s.replace(old_changes, new_changes).replace(old_untracked, new_untracked)

# Extra safety: ensure we did exactly 2 replacements
if s2 == s:
    print("ERROR: no changes applied.", file=sys.stderr)
    sys.exit(3)

tmp = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else None
PY "$TMP"

# The python above writes to TMP via argv; do that now:
python3 - <<'PY'
import pathlib, sys
src = pathlib.Path.home() / "0luka/interface/frontends/raycast/atg_multi_snap.zsh"
dst = pathlib.Path(sys.argv[1])
dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
PY "$TMP"

# Re-run patching but actually write the modified content to TMP
python3 - <<'PY'
import pathlib, sys

target = pathlib.Path.home() / "0luka/interface/frontends/raycast/atg_multi_snap.zsh"
tmp = pathlib.Path(sys.argv[1])

s = target.read_text(encoding="utf-8")

old_changes = '''echo "$st" | grep -v '^\\?\\?' | head -n "$D_CHANGED" || echo "(none)"'''
new_changes = '''echo "$st" | grep -E '^[ MADRC][MADRC]' | head -n "$D_CHANGED" || echo "(none)"'''

old_untracked = '''echo "$st" | grep '^\\?\\?' | head -n "$D_UNTRACKED" || echo "(none)"'''
new_untracked = '''echo "$st" | grep '^\\?\\?' | head -n "$D_UNTRACKED" || echo "(none)"'''

if old_changes not in s or old_untracked not in s:
    raise SystemExit("ERROR: patterns not found after escape-normalization; abort")

s = s.replace(old_changes, new_changes).replace(old_untracked, new_untracked)
tmp.write_text(s, encoding="utf-8")
PY "$TMP"

zsh -n "$TMP"
chmod +x "$TMP"
mv -f "$TMP" "$TARGET"
chmod +x "$TARGET"

echo "OK: patched $(basename "$TARGET") (git Changes/Untracked fixed)"

echo "Smoke: snapshot sections"
"$TARGET" --dry-run | awk '
  /^## Changes/ {p=1}
  /^## Untracked/ {p=1}
  /^---/ {p=0}
  p {print}
' | sed -n '1,40p'
