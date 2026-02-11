#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$PWD}"
cd "$ROOT"

mkdir -p state/librarian

PENDING="state/librarian/pending.yaml"

if [[ ! -f "$PENDING" ]]; then
  cat > "$PENDING" <<'YAML'
# Approved v1 - pending contract (minimal scaffold)
conflict_policy: error
items: []
YAML
  echo "OK: created $PENDING"
else
  echo "OK: exists $PENDING"
fi

# Run
python3 -m tools.librarian.apply "$PENDING"

echo "OK: librarian apply finished"
