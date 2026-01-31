#!/usr/bin/env zsh
# tools/briefing/_launchd_briefing_runner.zsh
set -euo pipefail
umask 022

HERE="$(cd "$(dirname "$0")" && pwd -P)"
ROOT="$(cd "$HERE/../.." && pwd -P)"

TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
OUT="$ROOT/logs/components/dashboard_briefing/current.log"
ERR="$ROOT/logs/components/dashboard_briefing/error.log"

mkdir -p "$(dirname "$OUT")"

{
  echo "[$TS] dashboard_briefing heart-beat"
  export LUKA_ROOT="$ROOT"
  zsh "$ROOT/tools/briefing/build_briefing.zsh"
  echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] dashboard_briefing finished | exit=0"
} >>"$OUT" 2>>"$ERR"
