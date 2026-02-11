#!/usr/bin/env zsh
# A2-Phase 1: Lease TTL Verification script
set -euo pipefail

ROOT="${ROOT:-/Users/icmini/0luka}"
LEASE_DIR="$ROOT/runtime/job_leases"
API_URL="http://127.0.0.1:7001/api/jobs"
EVID_DIR="/Users/icmini/opal_a2_evidence/p1_$(date +%Y%m%dT%H%M%SZ)"

mkdir -p "$EVID_DIR"
echo "[A2-P1] Evidence Dir: $EVID_DIR"

# 1. Lease Creation & Renewal Test
echo "[A2-P1] 1. Submitting long-running job..."
echo "dummy" > dummy_job.txt
JOB_ID=$(curl -sS -X POST "$API_URL" \
  -F "prompt=SLEEP_TEST_30s" \
  -F "input_file=@dummy_job.txt" \
  -F "metadata={\"engine\":\"mock_engine_v1\"}" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])")

echo "[A2-P1] Job ID: $JOB_ID"

echo "[A2-P1] Waiting for job to be claimed..."
# Wait up to 5s for the lease to appear
for i in {1..10}; do
  if [[ -f "$LEASE_DIR/$JOB_ID.json" ]]; then
    echo "[A2-P1] Lease file created: $LEASE_DIR/$JOB_ID.json"
    break
  fi
  sleep 0.5
done

if [[ ! -f "$LEASE_DIR/$JOB_ID.json" ]]; then
    echo "[A2-P1] FAIL: Lease file NOT found."
    exit 1
fi

echo "[A2-P1] Waiting 10s to test renewal (Renew interval: 5s)..."
current_renew=$(python3 -c "import json; print(json.load(open('$LEASE_DIR/$JOB_ID.json'))['last_renewed_at'])")
sleep 10
new_renew=$(python3 -c "import json; print(json.load(open('$LEASE_DIR/$JOB_ID.json'))['last_renewed_at'])")

if [[ "$current_renew" == "$new_renew" ]]; then
    echo "[A2-P1] FAIL: Lease NOT renewed (Before: $current_renew, After: $new_renew)"
    exit 4
fi
echo "[A2-P1] Lease renewed OK ($new_renew)"

# 2. Kill Test (Reclaim)
# We want to kill the worker that has THIS job.
worker_id=$(python3 -c "import json; print(json.load(open('$LEASE_DIR/$JOB_ID.json'))['worker_id'])")
pid=$(python3 -c "import json; print(json.load(open('$LEASE_DIR/$JOB_ID.json'))['meta']['pid'])")

echo "[A2-P1] Worker ID: $worker_id, PID: $pid"
echo "[A2-P1] Killing worker..."
kill -9 "$pid"

echo "[A2-P1] Monitoring lease expiry (Default TTL=15s)..."
# Wait up to 60s
for i in {1..60}; do
    resp=$(curl -sS "$API_URL/$JOB_ID")
    job_status=$(echo "$resp" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('status',''))" 2>/dev/null || echo "unknown")
    echo "[A2-P1] Job Status: $job_status"
    if [[ "$job_status" == "failed" ]]; then
        break
    fi
    sleep 1
done

final_job=$(curl -sS "$API_URL/$JOB_ID")
final_status=$(echo "$final_job" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('status',''))" 2>/dev/null || echo "error")
final_error=$(echo "$final_job" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('error',{}).get('message',''))" 2>/dev/null || echo "none")

echo "[A2-P1] Final Status: $final_status"
echo "[A2-P1] Final Error: $final_error"

if [[ "$final_status" == "failed" && "$final_error" == "lease_expired_reclaimed_a2" ]]; then
    echo "[A2-P1] PASS ✅"
    exit 0
else
    echo "[A2-P1] FAIL: Job not reclaimed correctly (Status: $final_status, Error: $final_error)"
    exit 2
fi
