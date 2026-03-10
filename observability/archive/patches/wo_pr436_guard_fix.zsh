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

# Replace the os.readlink resolve line with safer block
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

# 2) Safety: ensure no data loss on failed recovery
# This is deliberately conservative: we only proceed with heal if move_to_recovered() returns True.
python3 - <<'PY'
from pathlib import Path
import re

p = Path("tools/guardrails/mls_symlink_guard.py")
s = p.read_text(encoding="utf-8")

# Heuristic patch:
# - find call-sites where a violating regular file is handled
# - ensure code branches on success of move_to_recovered before unlink/replace
# NOTE: This patch is minimal and may require small manual adjust if your function names differ.

# 2a) Strengthen move_to_recovered() to temp+atomic rename if function exists
if "def move_to_recovered" in s and "os.replace(" not in s:
    # Try to insert atomic temp rename approach in function body.
    # We will only do a light-touch insertion if we find a return True/False pattern.
    pass

# 2b) Guard call-site: require success before continuing heal
# Replace: move_to_recovered(...); recreate_symlink(...)
# with: if not move_to_recovered(...): log + continue
pattern = r"(move_to_recovered\([^\)]*\)\s*\n)(\s*)(recreate_|relink_|create_).*"
m = re.search(pattern, s)
if not m:
    print("WARN: could not auto-locate call-site for move_to_recovered() gating. You should enforce: if not move_to_recovered: continue")
else:
    indent = m.group(2)
    repl = f"if not {m.group(1).strip()}:\n{indent}    log_violation(..., severity=\"error\", msg=\"recover_failed; skip_heal\")\n{indent}    continue\n{indent}{m.group(3)}"
    # This is too context-dependent to safely apply automatically without your exact code.
    print("WARN: safety gating is context-dependent; please apply manually in Codex IDE using the instructions.")
PY

git diff --stat
echo ""
echo "NOTE: Applied Patch A (relative symlink resolve). Patch B (no-delete-on-failed-recover) should be applied via Codex IDE due to context sensitivity."
