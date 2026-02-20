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

LINT_ARGS=("$@")
if [[ ${#LINT_ARGS[@]} -eq 0 ]]; then
  LINT_ARGS=(--json)
fi

exec "$ROOT/tools/ops/safe_run.zsh" "${SAFE_ARGS[@]}" -- python3 "$ROOT/tools/ops/activity_feed_linter.py" "${LINT_ARGS[@]}"
