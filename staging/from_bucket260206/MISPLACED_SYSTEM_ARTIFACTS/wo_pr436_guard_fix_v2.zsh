#!/usr/bin/env zsh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

FILE="tools/guardrails/mls_symlink_guard.py"

if [[ ! -f "$FILE" ]]; then
  echo "ERROR: missing $FILE"
  exit 1
fi

python3 - <<'PY'
from pathlib import Path
import re, sys

p = Path("tools/guardrails/mls_symlink_guard.py")
s = p.read_text(encoding="utf-8")

# --- Detect already-patched state (relative resolution) ---
already = (
    "link_path.parent" in s and
    "os.path.isabs" in s and
    "raw = os.readlink" in s
)

if already:
    print("OK: Patch A already present (relative symlink resolution). Skipping.")
    sys.exit(0)

# --- Try to patch verify_symlink() in a robust way ---
# We look for the verify_symlink function body and replace the return line that compares readlink.
m = re.search(r"def\s+verify_symlink\s*\(.*?\):\n(?P<body>(?:\s+.*\n)+?)\n", s)
if not m:
    print("ERROR: cannot locate verify_symlink() function block")
    sys.exit(1)

body = m.group("body")

# Find a line that returns something like Path(os.readlink(...)).resolve() == target.resolve()
ret = re.search(r"^\s*return\s+Path\(os\.readlink\(link_path\)\)\.resolve\(\)\s*==\s*target\.resolve\(\)\s*$", body, re.M)
if not ret:
    print("ERROR: cannot find expected return comparison inside verify_symlink(); file may be customized already.")
    sys.exit(1)

replacement = """raw = os.readlink(link_path)
        if os.path.isabs(raw):
            resolved = Path(raw).resolve()
        else:
            resolved = (link_path.parent / raw).resolve()
        return resolved == target.resolve()"""

new_body = body[:ret.start()] + re.sub(r"^\s*return.*$", replacement, body[ret.start():ret.end()], flags=re.M) + body[ret.end():]
s2 = s[:m.start("body")] + new_body + s[m.end("body"):]
p.write_text(s2, encoding="utf-8")
print("OK: Applied Patch A (relative symlink resolution) to verify_symlink().")
PY

echo ""
echo "=== Diff stat ==="
git diff --stat

echo ""
echo "=== verify_symlink snippet (for sanity) ==="
python3 - <<'PY'
from pathlib import Path
import re

p = Path("tools/guardrails/mls_symlink_guard.py")
s = p.read_text(encoding="utf-8")

m = re.search(r"def\s+verify_symlink\s*\(.*?\):\n(?:\s+.*\n)+?\n", s)
if not m:
    print("Cannot locate verify_symlink")
else:
    block = m.group(0).rstrip()
    print(block)
PY

echo ""
echo "NOTE: Patch B (no-delete-on-failed-recover) is NOT applied here; do it in Codex IDE based on actual move_to_recovered() + call-site."
