#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
ROOT="${ROOT%/}"

SAFE_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --force|--no-refresh)
      SAFE_ARGS+=("$1")
      shift
      ;;
    --)
      shift
      break
      ;;
    *)
      break
      ;;
  esac
done

PYTEST_ARGS=("$@")
if [[ ${#PYTEST_ARGS[@]} -eq 0 ]]; then
  PYTEST_ARGS=(tests/ -q)
fi

exec "$ROOT/tools/ops/safe_run.zsh" "${SAFE_ARGS[@]}" -- python3 -m pytest "${PYTEST_ARGS[@]}"
