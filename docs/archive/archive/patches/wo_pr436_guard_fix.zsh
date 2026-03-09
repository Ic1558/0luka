#!/usr/bin/env zsh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

FILE="tools/guardrails/mls_symlink_guard.py"

# 1) Patch: resolve relative symlink targets against link_path.parent
python3 - <<'PY'
from pathlib import Path
import re

p = Path("tools/guardrails/mls_symlink_guard.py")
s = p.read_text(encoding="utf-8")

old = "return Path(os.readlink(link_path)).resolve() == target.resolve()"
if old not in s:
    print("ERROR: expected pattern not found for verify_symlink() patch")
    raise SystemExit(1)

new = """raw = os.readlink(link_path)
        if os.path.isabs(raw):
            resolved = Path(raw).resolve()
        else:
            resolved = (link_path.parent / raw).resolve()
        return resolved == target.resolve()"""

s2 = s.replace(old, new, 1)
p.write_text(s2, encoding="utf-8")
print("OK: patched verify_symlink() relative-target handling")
PY

git diff --stat
echo ""
echo "NOTE: Applied Patch A (relative symlink resolve). Patch B (no-delete-on-failed-recover) should be applied via Codex IDE due to context sensitivity."
