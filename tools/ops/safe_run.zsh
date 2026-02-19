#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
ROOT="${ROOT%/}"

FORCE="0"
REFRESH="1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE="1"
      shift
      ;;
    --no-refresh)
      REFRESH="0"
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

if [[ $# -eq 0 ]]; then
  echo "usage: tools/ops/safe_run.zsh [--force] [--no-refresh] -- <command...>" >&2
  exit 64
fi

if [[ "$REFRESH" == "1" ]]; then
  if ! ROOT="$ROOT" bash "$ROOT/tools/ram_monitor.zsh" >/dev/null 2>&1; then
    echo "safe_run: ram_monitor_refresh_failed" >&2
    exit 43
  fi
fi

TEL_JSON="$ROOT/observability/telemetry/ram_monitor.latest.json"
if [[ ! -f "$TEL_JSON" ]]; then
  echo "safe_run: telemetry_missing:$TEL_JSON" >&2
  exit 43
fi

RAM_INFO="$(TEL_JSON="$TEL_JSON" python3 - <<PY
import json
import os
from pathlib import Path

path = Path(os.environ['TEL_JSON'])
obj = json.loads(path.read_text(encoding='utf-8'))
level = str(obj.get('pressure_level', '')).strip().upper()
rec = str(obj.get('recommendation', '')).strip()
free_b = int(obj.get('free_bytes', 0) or 0)
comp_b = int(obj.get('compressed_bytes', 0) or 0)
suggest = obj.get('suggest_kill_list', [])
if not isinstance(suggest, list):
    suggest = []

print(f"LEVEL={level}")
print(f"RECOMMENDATION={rec}")
print(f"FREE_MB={int(free_b/1024/1024)}")
print(f"COMPRESSED_GB={(comp_b/1024/1024/1024):.1f}")
safe = []
for row in suggest:
    if not isinstance(row, dict):
        continue
    name = str(row.get('name', ''))
    cmdline = str(row.get('cmdline', ''))
    hay = f"{name} {cmdline}".lower()
    if any(x in hay for x in ("codex", "dispatcher", "redis", "ollama")):
        continue
    safe.append(row)

for i, row in enumerate(safe[:3], start=1):
    if not isinstance(row, dict):
        continue
    pid = row.get('pid', '')
    name = str(row.get('name', ''))
    rss = row.get('rss_mb', '')
    print(f"SUGGEST_{i}=pid:{pid} name:{name} rss_mb:{rss}")
PY
)"

LEVEL=""
RECOMMENDATION=""
FREE_MB="0"
COMPRESSED_GB="0"
SUGGEST_1=""
SUGGEST_2=""
SUGGEST_3=""
while IFS='=' read -r key val; do
  case "$key" in
    LEVEL) LEVEL="$val" ;;
    RECOMMENDATION) RECOMMENDATION="$val" ;;
    FREE_MB) FREE_MB="$val" ;;
    COMPRESSED_GB) COMPRESSED_GB="$val" ;;
    SUGGEST_1) SUGGEST_1="$val" ;;
    SUGGEST_2) SUGGEST_2="$val" ;;
    SUGGEST_3) SUGGEST_3="$val" ;;
  esac
done <<< "$RAM_INFO"

if [[ -n "${SAFE_RUN_FORCE_LEVEL:-}" ]]; then
  LEVEL="${SAFE_RUN_FORCE_LEVEL:u}"
fi

if [[ -z "$LEVEL" ]]; then
  echo "safe_run: invalid_ram_telemetry_missing_pressure_level" >&2
  exit 43
fi

if [[ "$LEVEL" == "CRITICAL" ]]; then
  echo "safe_run: blocked level=CRITICAL free_mb=$FREE_MB compressed_gb=$COMPRESSED_GB recommendation=$RECOMMENDATION" >&2
  if [[ -n "$SUGGEST_1" ]]; then echo "safe_run: suggest_kill_list:" >&2; fi
  [[ -n "$SUGGEST_1" ]] && echo "  - $SUGGEST_1" >&2
  [[ -n "$SUGGEST_2" ]] && echo "  - $SUGGEST_2" >&2
  [[ -n "$SUGGEST_3" ]] && echo "  - $SUGGEST_3" >&2
  exit 42
fi

if [[ "$LEVEL" == "WARN" && "$FORCE" != "1" ]]; then
  echo "safe_run: blocked level=WARN (require --force) free_mb=$FREE_MB compressed_gb=$COMPRESSED_GB recommendation=$RECOMMENDATION" >&2
  exit 41
fi

echo "safe_run: allow level=$LEVEL command=$*"
"$@"
