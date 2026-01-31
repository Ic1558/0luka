#!/usr/bin/env zsh
set -euo pipefail
umask 022

HERE="$(cd "$(dirname "$0")" && pwd -P)"
ROOT="$(cd "$HERE/../.." && pwd -P)"

TS="$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"))
PY
)"

OUT="$ROOT/logs/components/lisa_executor/current.log"
ERR="$ROOT/logs/components/lisa_executor/error.log"

{
  echo "[$TS] lisa_executor heart-beat"
  python3 "$ROOT/tools/bridge/lisa_executor.py" --root "$ROOT"
  TS2="$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"))
PY
)"
  echo "[$TS2] lisa_executor finished | exit=0"
} >>"$OUT" 2>>"$ERR"
