#!/usr/bin/env zsh
# phase_o_fix_current_logs.zsh — ensure logs/components/*/current.log is readable
# Usage: zsh tools/ops/phase_o_fix_current_logs.zsh [ROOT]
# ROOT defaults to $PWD. Touches or gunzips current.log where missing.
set -euo pipefail

ROOT="${1:-$PWD}"
cd "$ROOT"

fix_one() {
  local dir="$1"
  local plain="$dir/current.log"
  local gz="$dir/current.log.gz"

  if [[ -f "$plain" ]]; then
    return 0
  fi

  if [[ -f "$gz" ]]; then
    gzip -dc "$gz" > "$plain"
    return 0
  fi

  # Fallback: symlink newest dated log -> current.log
  local newest
  newest="$(ls -1t "$dir"/*.log(N) 2>/dev/null | head -n 1 || true)"
  if [[ -n "${newest:-}" ]]; then
    ln -sf "$(basename "$newest")" "$plain"
  fi
}

for d in logs/components/*(/); do
  fix_one "$d"
done

echo "OK: ensured readable logs/components/*/current.log where possible"
ls -la logs/components/phase_o_daily 2>/dev/null | sed -n '1,60p' || true
