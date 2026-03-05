#!/usr/bin/env bash

set -euo pipefail

RUNTIME_ROOT="${LUKA_RUNTIME_ROOT:-/Users/icmini/0luka_runtime}"

echo "=== Baseline ==="
# Notice since there are pre-existing unsealed segments, baseline might fail on the actual system unless we use temp
python3 tools/ops/audit_feed_segments.py --runtime-root "$RUNTIME_ROOT" || true

echo ""
echo "=== Corruption Simulation Tests (on temp copy) ==="
TMP_RT="/tmp/luka_segment_audit_tests"
rm -rf "$TMP_RT"
mkdir -p "$TMP_RT/logs/archive"

# Setup dummy segments for testing
S1="activity_feed.20260305T000000Z.jsonl"
cat << 'EOF' > "$TMP_RT/logs/archive/$S1"
{"ts_utc":"2026-03-05T00:00:00Z","action":"x","hash":"hash1","prev_hash":"hash0"}
{"ts_utc":"2026-03-05T00:00:01Z","action":"x","hash":"hash2","prev_hash":"hash1"}
EOF

S2="activity_feed.jsonl"
cat << 'EOF' > "$TMP_RT/logs/activity_feed.jsonl"
{"ts_utc":"2026-03-05T00:00:02Z","action":"x","hash":"hash3","prev_hash":"hash2"}
EOF

SEAL_HASH=$(python3 -c "import hashlib; print(hashlib.sha256(b'${S1}hash1hash22').hexdigest())")
cat << EOF > "$TMP_RT/logs/rotation_seals.jsonl"
{"segment_name":"$S1","first_hash":"hash1","last_hash":"hash2","line_count":2,"seal_hash":"$SEAL_HASH","sealed_at_utc":"2026-03-05T00:00:01.5Z"}
EOF

echo "--- Baseline (Temp Copy) ---"
python3 tools/ops/audit_feed_segments.py --runtime-root "$TMP_RT" || true

echo ""
echo "--- Test A: Truncate Segment Copy ---"
cp -a "$TMP_RT" "$TMP_RT-A"
# Remove the last line from S1
sed -i '' '$d' "$TMP_RT-A/logs/archive/$S1"
python3 tools/ops/audit_feed_segments.py --runtime-root "$TMP_RT-A" --deep || true

echo ""
echo "--- Test B: Mutate Byte (Hash Chain Break) ---"
cp -a "$TMP_RT" "$TMP_RT-B"
# Change hash1 to hasht in S1
sed -i '' 's/hash1/hasht/g' "$TMP_RT-B/logs/archive/$S1"
python3 tools/ops/audit_feed_segments.py --runtime-root "$TMP_RT-B" --deep || true

echo ""
echo "--- Test C: Reorder Segment Sequence ---"
cp -a "$TMP_RT" "$TMP_RT-C"
# rename to invalid time
mv "$TMP_RT-C/logs/archive/$S1" "$TMP_RT-C/logs/archive/activity_feed.invalid.jsonl"
python3 tools/ops/audit_feed_segments.py --runtime-root "$TMP_RT-C" || true

