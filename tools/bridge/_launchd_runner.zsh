#!/usr/bin/env zsh
set -euo pipefail
umask 022

HERE="$(cd "$(dirname "$0")" && pwd -P)"
ROOT="$(cd "$HERE/../.." && pwd -P)"

LOG_DIR="$ROOT/observability/logs"
mkdir -p "$LOG_DIR"

ts="$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"))
PY
)"

echo "[$ts] inbox_bridge heart-beat"

PYTHON="python3"
if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
fi

"$PYTHON" "$ROOT/tools/bridge/inbox_to_pending.py" \
  "$ROOT" \
  "$ROOT/state/inbox/new" \
  "$ROOT/state/inbox/processing" \
  "$ROOT/state/librarian/pending.yaml"

