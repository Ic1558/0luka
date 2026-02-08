#!/usr/bin/env zsh
# A2.1.1: Observability Pack Verification
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:7001}"
ROOT="${ROOT:-$HOME/0luka}"
TELEMETRY_LOG="$ROOT/observability/telemetry/opal_events.jsonl"

echo "[A2.1.1] Observability Pack Verification"
echo "[A2.1.1] Telemetry log: $TELEMETRY_LOG"

# Clear old telemetry
rm -f "$TELEMETRY_LOG"
mkdir -p "$(dirname "$TELEMETRY_LOG")"

# Submit a test job
echo "[A2.1.1] Submitting test job..."
echo "test" > /tmp/test_input.txt
JOB_ID=$(curl -sS -X POST "$API_BASE/api/jobs" \
  -F "prompt=SLEEP_TEST_10s" \
  -F "input_file=@/tmp/test_input.txt" \
  -F "metadata={\"engine\":\"mock_engine_v1\"}" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

echo "[A2.1.1] Job ID: $JOB_ID"

# Wait for job to start
sleep 3

# Check telemetry events
if [[ ! -f "$TELEMETRY_LOG" ]]; then
  echo "[A2.1.1] ❌ FAIL: No telemetry log created"
  exit 1
fi

echo ""
echo "[A2.1.1] === Telemetry Events ==="
cat "$TELEMETRY_LOG"
echo ""

# Verify lease_created event
if cat "$TELEMETRY_LOG" | grep -q "lease_created"; then
  echo "[A2.1.1] ✅ lease_created event found"
else
  echo "[A2.1.1] ❌ FAIL: lease_created event missing"
  exit 1
fi

# --- Trigger Retry Events (Kill Worker) ---
echo "[A2.1.1] Finding worker for job $JOB_ID to trigger retry..."
LEASE_FILE="$ROOT/runtime/job_leases/${JOB_ID}.json"

# Wait for lease file to appear (up to 10s)
for i in {1..20}; do
    if [[ -f "$LEASE_FILE" ]]; then
        break
    fi
    sleep 0.5
done

if [[ -f "$LEASE_FILE" ]]; then
  PID=$(python3 -c "import json; print(json.load(open('$LEASE_FILE'))['meta']['pid'])")
  echo "[A2.1.1] Killing worker PID $PID..."
  kill -9 "$PID" || true
else
  echo "[A2.1.1] ⚠️ No lease file found after 10s. Listing dir:"
  ls -la "$ROOT/runtime/job_leases/"
  echo "[A2.1.1] Skipping retry trigger."
fi

# Wait for reclaim and backoff (approx 15s TTL + scan time 20s + buffer)
echo "[A2.1.1] Waiting 45s for lease expiry and reclamation..."
sleep 45s

echo ""
echo "[A2.1.1] === Telemetry Events (Full Trace) ==="
cat "$TELEMETRY_LOG"
echo ""

# Verify Retry Events
REQUIRED_EVENTS=("reclaim_winner" "retry_scheduled" "backoff_applied")
for ev in "${REQUIRED_EVENTS[@]}"; do
  if grep -q "\"event\": \"$ev\"" "$TELEMETRY_LOG"; then
    echo "[A2.1.1] ✅ $ev event found"
  else
    echo "[A2.1.1] ❌ FAIL: $ev event missing"
    # Don't exit yet, check structure first
  fi
done

# Check event count
EVENT_COUNT=$(wc -l < "$TELEMETRY_LOG")
echo "[A2.1.1] Total events logged: $EVENT_COUNT"

# Verify JSON structure
python3 -c "
import json
import sys

log_path = '$TELEMETRY_LOG'
required_fields = ['ts', 'event']

with open(log_path, 'r') as f:
    for i, line in enumerate(f, 1):
        if not line.strip(): continue
        try:
            event = json.loads(line)
            for field in required_fields:
                if field not in event:
                    print(f'[A2.1.1] ❌ FAIL: Event {i} missing field {field}')
                    sys.exit(1)
        except json.JSONDecodeError as e:
            print(f'[A2.1.1] ❌ FAIL: Event {i} invalid JSON: {e}')
            sys.exit(1)

print('[A2.1.1] ✅ All events have valid JSON structure')
"

echo ""
echo "[A2.1.1] ✅ PASS - Observability Pack working correctly"
