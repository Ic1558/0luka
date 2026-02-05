#!/usr/bin/env zsh
set -euo pipefail

ROOT="${1:-$PWD}"

ts="$(date +%y%m%d_%H%M%S)"
echo "ROOT=$ROOT"
echo "TS=$ts"

if ! command -v rg >/dev/null 2>&1; then
  echo "ERROR: ripgrep (rg) not found"
  exit 1
fi

# Find candidate files (limit to repo text files; adjust if you want wider)
mapfile -t files < <(rg -l "datetime\.datetime\.utcnow\(\)" "$ROOT" || true)

if (( ${#files[@]} == 0 )); then
  echo "OK: no utcnow() usage found."
  exit 0
fi

echo "Found ${#files[@]} file(s) with datetime.datetime.utcnow():"
printf " - %s\n" "${files[@]}"

for f in "${files[@]}"; do
  echo "Patching: $f"

  cp -p "$f" "$f.bak.$ts"

  # Patch content via python (safe rewrite)
  python3 - <<PY
from pathlib import Path

p = Path(${f@q})
s = p.read_text(encoding="utf-8")

if "datetime.datetime.utcnow()" not in s:
    print("SKIP: pattern not present anymore:", p)
    raise SystemExit(0)

# 1) Replace utcnow() call
s2 = s.replace("datetime.datetime.utcnow()", "datetime.datetime.now(datetime.UTC)")

# 2) Ensure timezone-aware import is available when 'datetime.UTC' is referenced.
#    If file already uses 'datetime.' we only need to ensure 'import datetime' exists.
#    Many snippets already have it; if not, we try to inject it safely.
if "datetime.UTC" in s2 and "import datetime" not in s2:
    # Insert near top: after shebang if present, else at beginning.
    lines = s2.splitlines(True)
    insert_at = 1 if (lines and lines[0].startswith("#!")) else 0
    lines.insert(insert_at, "import datetime\\n")
    s2 = "".join(lines)

p.write_text(s2, encoding="utf-8")
print("OK:", p)
PY

done

echo ""
echo "DONE: patched utcnow() -> now(datetime.UTC)"
echo "Backups: *.bak.$ts"
echo ""
echo "Next suggested checks:"
echo "  rg -n \"utcnow\\(\\)\" \"$ROOT\" || true"
echo "  rg -n \"datetime\\.UTC\" \"$ROOT\" || true"
