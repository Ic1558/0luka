#!/bin/zsh
# bootstrap_runtime.zsh — idempotent runtime root setup
# Creates ~/0luka_runtime/ directory tree required before LUKA_RUNTIME_ROOT services start.
# Safe to run multiple times. Does not overwrite existing files.
set -euo pipefail

RUNTIME_ROOT="${LUKA_RUNTIME_ROOT:-$HOME/0luka_runtime}"

echo "Bootstrap: $RUNTIME_ROOT"
for d in \
  logs \
  logs/index \
  logs/archive \
  artifacts \
  "artifacts/sovereign_runs" \
  tmp \
  locks; do
  mkdir -p "$RUNTIME_ROOT/$d"
done

# Write .env only if not already present
ENV_FILE="$RUNTIME_ROOT/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  printf 'export LUKA_RUNTIME_ROOT=%s\n' "$RUNTIME_ROOT" > "$ENV_FILE"
fi

echo "Bootstrap complete: $RUNTIME_ROOT"
echo "  Source with: source $ENV_FILE"
