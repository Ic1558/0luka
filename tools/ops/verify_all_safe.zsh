#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$PWD}"
cd "$ROOT"

SAFE_RUN="${ROOT}/tools/ops/safe_run.zsh"
PYTEST_SAFE="${ROOT}/tools/ops/pytest_safe.zsh"
LINT_SAFE="${ROOT}/tools/ops/lint_safe.zsh"
LINTER="${ROOT}/tools/ops/activity_feed_linter.py"

# Single canonical entrypoint. Everything funnels through safe_run.
# - OK: runs
# - WARN: blocks unless --force (handled by safe_run)
# - CRITICAL: blocks (handled by safe_run)
#
# Usage:
#   ROOT="$PWD" zsh tools/ops/verify_all_safe.zsh [--force]
#
# NOTE: keep this script “dumb”: delegate policy to safe_run.

ARGS=("$@")

# Run pytest gate (safe)
"$SAFE_RUN" "${ARGS[@]}" -- zsh "$PYTEST_SAFE"

# Run lint gate (safe)
"$SAFE_RUN" "${ARGS[@]}" -- zsh "$LINT_SAFE"

# Always run canonical activity feed linter (non-runtime lane; ops-only)
python3 "$LINTER" --json >/dev/null

echo "OK: verify_all_safe"
