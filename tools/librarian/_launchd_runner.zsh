#!/usr/bin/env zsh
set -euo pipefail
umask 022

# launchd env is minimal
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# resolve repo ROOT from this file location: tools/librarian/_launchd_runner.zsh
HERE="$(cd "$(dirname "$0")" && pwd -P)"
ROOT="$(cd "$HERE/../.." && pwd -P)"

PENDING="$ROOT/state/librarian/pending.yaml"
SNAPDIR="$ROOT/state/librarian/snapshots"
OUTLOG="$ROOT/observability/logs/librarian_apply.launchd.out.log"
ERRLOG="$ROOT/observability/logs/librarian_apply.launchd.err.log"

FAIL_MARKER="$ROOT/state/librarian/last_error.json"
FAIL_COUNT_FILE="$ROOT/state/librarian/fail_count.txt"
PAUSE="$ROOT/state/librarian/PAUSE"
FAIL_MAX="${FAIL_MAX:-3}"

mkdir -p "$ROOT/state/librarian" "$SNAPDIR" "$ROOT/observability/logs"

ts_now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

# --- PAUSE switch ---
if [[ -f "$PAUSE" ]]; then
  TS="$(ts_now)"
  echo "[$TS] librarian paused (PAUSE switch present)" >> "$OUTLOG"
  exit 0
fi

# --- snapshot ring buffer for current_system.json (keep last 10) ---
if [[ -f "$ROOT/state/current_system.json" ]]; then
  TS="$(date -u +"%Y%m%dT%H%M%SZ")"
  cp -p "$ROOT/state/current_system.json" "$SNAPDIR/current_system.${TS}.json" 2>/dev/null || true
  # keep last 10
  ls -1t "$SNAPDIR"/current_system.*.json 2>/dev/null | tail -n +11 | xargs -I{} rm -f "{}" 2>/dev/null || true
fi

# --- pending_count (safe) ---
pending_count="$(
python3 - <<'PY'
from pathlib import Path
p = Path("state/librarian/pending.yaml")
if not p.exists():
    print(0); raise SystemExit(0)
try:
    import yaml
except Exception:
    print(0); raise SystemExit(0)
obj = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
items = obj.get("moves") or obj.get("items") or obj.get("actions") or []
print(len(items) if isinstance(items, list) else 0)
PY
)" || pending_count="0"
if ! [[ "$pending_count" =~ '^[0-9]+$' ]]; then pending_count="0"; fi

# --- run apply (capture exit) ---
TS="$(ts_now)"
echo "[$TS] librarian heart-beat" >> "$OUTLOG"

set +e
python3 -m tools.librarian.apply "$PENDING" >> "$OUTLOG" 2>> "$ERRLOG"
APPLY_EXIT=$?
set -e

# --- circuit breaker / failure marker ---
if [[ $APPLY_EXIT -ne 0 ]]; then
  FC="0"
  if [[ -f "$FAIL_COUNT_FILE" ]]; then
    FC="$(cat "$FAIL_COUNT_FILE" 2>/dev/null || echo 0)"
  fi
  if ! [[ "$FC" =~ '^[0-9]+$' ]]; then FC="0"; fi
  FC=$((FC+1))
  echo "$FC" > "$FAIL_COUNT_FILE"

  python3 - <<PY2
import json, pathlib
p = pathlib.Path("$FAIL_MARKER")
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({
  "ts_utc": "$TS",
  "exit_code": int("$APPLY_EXIT"),
  "reason": "librarian_apply_failed",
  "fail_count": int("$FC"),
}, indent=2) + "\n", encoding="utf-8")
PY2

  if [[ $FC -ge $FAIL_MAX ]]; then
    : > "$PAUSE"
    echo "[$TS] librarian circuit_breaker engaged | exit=$APPLY_EXIT fail_count=$FC" >> "$OUTLOG"
  else
    echo "[$TS] librarian failed | exit=$APPLY_EXIT fail_count=$FC" >> "$OUTLOG"
  fi

  echo "[$TS] librarian finished | ts_utc=$TS exit=$APPLY_EXIT pending_count=$pending_count noop=false" >> "$OUTLOG"
  exit $APPLY_EXIT
else
  echo "0" > "$FAIL_COUNT_FILE" 2>/dev/null || true
  rm -f "$FAIL_MARKER" 2>/dev/null || true

  noop="true"
  if [[ "$pending_count" -gt 0 ]]; then noop="false"; fi
  echo "[$TS] librarian finished | ts_utc=$TS exit=0 pending_count=$pending_count noop=$noop" >> "$OUTLOG"
fi
