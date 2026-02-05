#!/usr/bin/env zsh
set -euo pipefail

cd ~/02luka

TARGET="tools/codex/skills"

echo "=== 0) Sanity ==="
git status -sb
echo

echo "=== 1) Show .gitmodules entry (if any) ==="
if [ -f .gitmodules ]; then
  grep -n "tools/codex/skills" .gitmodules || true
  echo
  echo "--- .gitmodules ---"
  cat .gitmodules
else
  echo "No .gitmodules file found."
fi
echo

echo "=== 2) Deinit submodule (safe even if missing) ==="
git submodule deinit -f "$TARGET" 2>/dev/null || true
rm -rf ".git/modules/$TARGET" 2>/dev/null || true
echo "OK"
echo

echo "=== 3) Remove gitlink from index (safe even if missing) ==="
git rm -f "$TARGET" 2>/dev/null || true
echo "OK"
echo

echo "=== 4) Remove stanza from .gitmodules (if exists) ==="
if [ -f .gitmodules ]; then
python3 - <<'PY'
import re, pathlib
p = pathlib.Path(".gitmodules")
s = p.read_text(encoding="utf-8")
pattern = r'\[submodule "tools/codex/skills"\]\n(?:[^\n]*\n)*?(?=\n\[submodule |\Z)'
new = re.sub(pattern, "", s, flags=re.M)
new = re.sub(r"\n{3,}", "\n\n", new).strip() + "\n"
p.write_text(new, encoding="utf-8")
PY
  git add .gitmodules
  echo "Updated .gitmodules"
else
  echo "No .gitmodules to edit"
fi
echo

echo "=== 5) Final check ==="
echo "Submodule url (should be empty now):"
git config -f .gitmodules --get submodule.tools/codex/skills.url 2>/dev/null || echo "(none)"
echo
git status -sb
echo

echo "=== 6) Commit ==="
git commit -m "fix(ci): remove broken codex skills submodule reference" || {
  echo "Nothing to commit."
  exit 0
}
echo

echo "=== 7) Push current branch ==="
BR="$(git branch --show-current)"
git push -u origin "$BR"
echo
echo "Done. Re-run PR checks."
