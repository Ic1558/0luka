#!/usr/bin/env zsh
set -euo pipefail
setopt nullglob

ROOT="$HOME/02luka"
OUT_DIR="$ROOT/g/telemetry"
OUT_FILE="$OUT_DIR/health_check_latest.json"

mkdir -p "$OUT_DIR"

# Candidate locations (expand if your generator writes somewhere else)
candidates=(
  "$ROOT/g/reports/health/health_*.json"
  "$ROOT/observability/quarantine/nonobs/**/g/reports/health/health_*.json"
  "$ROOT/telemetry/**/health*.json"
  "$ROOT/observability/**/health*.json"
)

echo "== Locate newest health snapshot =="
latest=""
for pat in "${candidates[@]}"; do
  # glob expansion
  for f in ${~pat}; do
    [[ -f "$f" ]] || continue
    if [[ -z "$latest" ]]; then
      latest="$f"
    else
      # compare mtime
      if [[ "$(stat -f %m "$f")" -gt "$(stat -f %m "$latest")" ]]; then
        latest="$f"
      fi
    fi
  done
done

if [[ -z "$latest" ]]; then
  echo "ERROR: no health snapshot json found in candidate paths."
  echo "Add your real generator output path into candidates[] and re-run."
  exit 2
fi

echo "Newest: $latest"
echo

echo "== Write compat latest pointer =="
cp -f "$latest" "$OUT_FILE"

# quick sanity: must be valid json (python exists per your env)
python3 - <<PY
import json,sys
p=r"""$OUT_FILE"""
with open(p,"r",encoding="utf-8") as f:
    json.load(f)
print("OK: valid JSON ->", p)
PY

echo
echo "== Done =="
ls -la "$OUT_FILE"
echo
echo "Next: restart/refresh Opal UI, it can now fetch:"
echo "  g/telemetry/health_check_latest.json"
