#!/usr/bin/env zsh
set -euo pipefail

cd "${1:-$HOME/02luka}"

echo "==[1] repo sanity"
git rev-parse --show-toplevel
git status --porcelain || true

echo "\n==[2] locate tk_guard + entrypoints"
command -v rg >/dev/null 2>&1 || { echo "ripgrep (rg) not found"; exit 2; }
rg -n --hidden --no-ignore-vcs --glob '!.git/' 'tk_guard|tk-guard|TK_GUARD|guard' . | head -n 200 || true

echo "\n==[3] run tests (best-effort)"
if [[ -f pyproject.toml || -f pytest.ini || -d tests ]]; then
  if command -v pytest >/dev/null 2>&1; then
    pytest -q -k 'tk_guard or guard' || true
  else
    python3 -m pytest -q -k 'tk_guard or guard' || true
  fi
else
  echo "No obvious pytest setup detected."
fi

echo "\n==[4] run make targets if present"
if [[ -f Makefile ]]; then
  for t in guard tk_guard test tests smoke; do
    if make -n "$t" >/dev/null 2>&1; then
      echo "Running: make $t"
      make "$t" || true
    fi
  done
fi

echo "\n==[5] quick negative/positive probes (only if a CLI exists)"
# Heuristic: look for likely CLI runners
candidates=(
  "g/tools/healthcheck.zsh"
  "g/sandbox/os_l0_l1/tools/healthcheck.zsh"
  "tools/healthcheck.zsh"
  "tools/guardcheck.zsh"
  "g/tools/guardcheck.zsh"
)
for f in $candidates; do
  if [[ -f "$f" ]]; then
    echo "Running: $f"
    zsh "$f" || true
  fi
done

echo "\n== DONE. Review output above. =="
