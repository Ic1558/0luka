#!/usr/bin/env zsh
# librarian_scaffold_v1.zsh — Generic "librarian apply" scaffold for YAML contracts.
# Usage: ROOT=/path/to/0luka zsh tools/ops/librarian_scaffold_v1.zsh
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

# Run librarian apply if tool exists
if [[ -f "tools/librarian/apply.py" ]]; then
    python3 -m tools.librarian.apply "$PENDING"
    echo "OK: librarian apply finished"
else
    echo "⚠️  tools/librarian/apply.py not found; scaffolded only."
fi
