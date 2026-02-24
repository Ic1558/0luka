#!/usr/bin/env zsh
# gmx_step6_pack6_proof_final.zsh
# Generate Pack6 Proof: Constitutional Activity Feed

set -euo pipefail

ROOT="/Users/icmini/0luka"
cd "$ROOT"

PACK_ID="$(date -u +"%Y%m%dT%H%M%SZ")_bf3_pack6_integrity"
PROOF_DIR="$ROOT/observability/artifacts/proof_packs/$PACK_ID"
mkdir -p "$PROOF_DIR"

echo "--- [1. Raw Feed Preservation] ---"
# We leverage the archive captured just before Pack 6 modifications
RAW_FEED_PATH="observability/logs/archive/activity_feed.20260224T192849Z.jsonl"
RAW_SHA256=$(shasum -a 256 "$RAW_FEED_PATH" | awk '{print $1}')

echo "--- [2. Linter Run Evidence] ---"
LINTER_OUT="$PROOF_DIR/linter_report.json"
python3 tools/ops/activity_feed_linter.py --strict --json > "$LINTER_OUT"

echo "--- [3. Guard Run Evidence] ---"
GUARD_OUT="$PROOF_DIR/guard_report.json"
# Run with --no-emit to just capture the current state as a report
python3 tools/ops/activity_feed_guard.py --once --json --no-emit > "$GUARD_OUT"

echo "--- [4. Escalation Evidence] ---"
# Find the specific lines in the feed
ESCALATION_EVENT=$(grep "system_pressure_unresolved" observability/logs/activity_feed.jsonl | tail -n 1)
ANOMALY_EVENT=$(grep "feed_anomaly" observability/logs/activity_feed.jsonl | tail -n 1)

# Generate Manifest
cat <<EOF > "$PROOF_DIR/manifest.json"
{
  "pack_id": "$PACK_ID",
  "ts_utc": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "raw_feed": {
    "path": "$RAW_FEED_PATH",
    "sha256": "$RAW_SHA256",
    "status": "preserved_pre_normalization"
  },
  "verifications": {
    "linter": {
      "command": "python3 tools/ops/activity_feed_linter.py --strict --json",
      "artifact": "linter_report.json"
    },
    "guard": {
      "command": "python3 tools/ops/activity_feed_guard.py --once --json",
      "artifact": "guard_report.json"
    }
  },
  "escalation_evidence": {
    "anomaly_event": $(echo "$ANOMALY_EVENT" | jq -c . || echo '"N/A"'),
    "escalation_event": $(echo "$ESCALATION_EVENT" | jq -c . || echo '"N/A"')
  }
}
EOF

MANIFEST_SHA256=$(shasum -a 256 "$PROOF_DIR/manifest.json" | awk '{print $1}')
echo "pack_6_proof_path=$PROOF_DIR"
echo "manifest_sha256=$MANIFEST_SHA256"
