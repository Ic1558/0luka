#!/usr/bin/env zsh
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
    # materialize a readable current.log (keeps gz as source of truth)
    gzip -dc "$gz" > "$plain"
    return 0
  fi

  # fallback: if only dated log exists, point current.log to newest dated file (not gz)
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
ls -la logs/components/phase_o_daily | sed -n '1,60p'
