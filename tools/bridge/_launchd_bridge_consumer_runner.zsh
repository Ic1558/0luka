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

OUT="$ROOT/logs/components/bridge_consumer/current.log"
ERR="$ROOT/logs/components/bridge_consumer/error.log"

{
  echo "[$TS] bridge_consumer heart-beat"
  python3 "$ROOT/tools/bridge/bridge_consumer.py" "$ROOT"
  TS2="$(python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"))
PY
)"
  echo "[$TS2] bridge_consumer finished | exit=0"
} >>"$OUT" 2>>"$ERR"
