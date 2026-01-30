#!/usr/bin/env zsh
set -euo pipefail
ROOT="${1:-$PWD}"
mkdir -p "$ROOT/logs/components/phase_o_daily"

# log this runner's own output
exec >> "$ROOT/logs/components/phase_o_daily/current.log" 2>&1

echo "=== Phase-O daily run: $(date -u +"%Y-%m-%dT%H:%M:%SZ") ==="

# rotate + summary (safe)
if [[ -x "$ROOT/tools/rotate_logs_min.zsh" ]]; then
  "$ROOT/tools/rotate_logs_min.zsh" "$ROOT" || true
else
  echo "WARN: missing tools/rotate_logs_min.zsh"
fi

if [[ -x "$ROOT/tools/build_summary_min.zsh" ]]; then
  "$ROOT/tools/build_summary_min.zsh" "$ROOT" || true
else
  echo "WARN: missing tools/build_summary_min.zsh"
fi

echo "=== done ==="
