#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
ROOT="${ROOT%/}"
export ROOT
ROOT_REF='${ROOT}'
OBS="$ROOT/observability"
OBS_REF="${ROOT_REF}/observability"
cd "$ROOT"

TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_DIR="$OBS/artifacts/followup"
TASK_DIR="$OBS/quarantine/tasks"
mkdir -p "$OUT_DIR" "$TASK_DIR"

OUT_JSON="$OUT_DIR/${TS}_followup.json"
TASK_YAML="$TASK_DIR/${TS}_followup.task.yaml"
OUT_JSON_REF="$OBS_REF/artifacts/followup/${TS}_followup.json"

# Minimal output artifact (replace later with real followup content)
cat > "$OUT_JSON" <<JSON
{
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "module": "followup_generator",
  "note": "Kernel v0 vertical-slice test artifact. Replace with real followup generation output next."
}
JSON

# sha256 (portable on macOS)
SHA="$(shasum -a 256 "$OUT_JSON" | awk '{print $1}')"

cat > "$TASK_YAML" <<YAML
actor: module.followup_generator
intent: action.followup.generate
meta:
  ts_utc: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  host: "$(hostname)"
artifacts:
  outputs:
    - path: "$OUT_JSON_REF"
      sha256: "$SHA"
verification:
  gates:
    - gate.fs.purity
    - gate.hash.match
    - gate.proc.clean
YAML

python3 "$ROOT/ops/core_kernel/router.py" "$TASK_YAML"
echo "OK: wrote $OUT_JSON_REF"
echo "OK: committed beacon line -> $OBS_REF/stl/ledger/global_beacon.jsonl"
