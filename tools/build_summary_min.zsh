#!/usr/bin/env zsh
set -euo pipefail

ROOT="${1:-$PWD}"
cd "$ROOT"

OUT="reports/summary/latest.md"
mkdir -p "$(dirname "$OUT")"

ts_local="$(date +'%Y-%m-%d %H:%M:%S %z')"
ts_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

{
  echo "# 0luka — Summary"
  echo
  echo "- generated_local: ${ts_local}"
  echo "- generated_utc: ${ts_utc}"
  echo "- cwd: $(pwd)"
  echo
  echo "## Signals"
  echo
  echo "### Recent incidents (if any)"
  if [[ -d "observability/incidents" ]]; then
    ls -1 "observability/incidents" 2>/dev/null | tail -n 10 | sed 's/^/- /' || true
  elif [[ -d "artifacts/incidents" ]]; then
    ls -1 "artifacts/incidents" 2>/dev/null | tail -n 10 | sed 's/^/- /' || true
  else
    echo "- (no incident directory found)"
  fi
  echo
  echo "### Latest open tasks"
  if [[ -d "artifacts/tasks/open" ]]; then
    ls -1 "artifacts/tasks/open" 2>/dev/null | tail -n 20 | sed 's/^/- /' || true
  else
    echo "- (no artifacts/tasks/open)"
  fi
  echo
  echo "## Log tails (current.log)"
  for d in logs/components/*; do
    [[ -d "$d" ]] || continue
    comp="$(basename "$d")"
    cur="$d/current.log"
    echo
    echo "### ${comp}"
    if [[ -f "$cur" ]]; then
      tail -n 30 "$cur" 2>/dev/null | sed 's/^/    /' || true
    else
      echo "    (missing current.log)"
    fi
  done
} > "$OUT"

echo "OK: wrote $OUT"
