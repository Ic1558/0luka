#!/usr/bin/env zsh
# A2-Phase 2.1: Retry Policy & Idempotency Verification
set -euo pipefail

ROOT="${ROOT:-/Users/icmini/0luka}"
API_URL="http://127.0.0.1:7001/api/jobs"
ARTIFACTS_DIR="$ROOT/runtime/opal_artifacts"
EVID_DIR="/Users/icmini/opal_a2_evidence/p2_$(date +%Y%m%dT%H%M%SZ)"

mkdir -p "$EVID_DIR"
echo "[A2-P2] Evidence Dir: $EVID_DIR"

# Helper for submitting jobs
submit_job() {
    local prompt=$1
    echo "dummy" > dummy_job.txt
    curl -sS -X POST "$API_URL" \
      -F "prompt=$prompt" \
      -F "input_file=@dummy_job.txt" \
      -F "metadata={\"engine\":\"mock_engine_v1\"}" | python3 -c "import sys, json; print(json.load(sys.stdin)['id'])"
}

# 1. Test Retry (Success on attempt 2)
echo "[A2-P2] 1. Testing Single Retry Success..."
JOB_ID=$(submit_job "SLEEP_TEST_20s_RETRY")
echo "[A2-P2] Job ID: $JOB_ID"

# Wait for lease to figure out PID
for i in {1..10}; do
    if [[ -f "$ROOT/runtime/job_leases/$JOB_ID.json" ]]; then break; fi
    sleep 0.5
done

pid=$(python3 -c "import json; print(json.load(open('$ROOT/runtime/job_leases/$JOB_ID.json'))['meta']['pid'])")
echo "[A2-P2] Killing worker (PID $pid)..."
kill -9 "$pid"

echo "[A2-P2] Monitoring reclamation and retry..."
# Reclaimer runs every 10 ticks. Loop until success or timeout (increased to 60s).
for i in {1..60}; do
    job_info=$(curl -sS "$API_URL/$JOB_ID")
    st=$(echo "$job_info" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "unknown")
    echo "[A2-P2] Status: $st (t=$i)"
    if [[ "$st" == "succeeded" ]]; then break; fi
    sleep 1
done

final_st=$(curl -sS "$API_URL/$JOB_ID" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status',''))")
if [[ "$final_st" == "succeeded" ]]; then
    echo "[A2-P2] Success! Checking artifacts..."
    ls -R "$ARTIFACTS_DIR/$JOB_ID"
    if [[ -d "$ARTIFACTS_DIR/$JOB_ID/attempt_1" && -d "$ARTIFACTS_DIR/$JOB_ID/attempt_2" ]]; then
        echo "[A2-P2] Isolation OK: Found attempt folders."
    else
        echo "[A2-P2] FAIL: Missing attempt isolation folders."
        exit 1
    fi
else
    echo "[A2-P2] FAIL: Job did not succeed after retry (Final Status: $final_st)."
    exit 2
fi

# 2. Test Max Retries (Fail after 2 retries)
echo "[A2-P2] 2. Testing Max Retries Exceeded..."
./runtime/launch_pool.zsh 5 & # Ensure full pool (background)
sleep 5 # Wait for workers to start
JOB_ID2=$(submit_job "SLEEP_TEST_30s_FAIL_MAX")
echo "[A2-P2] Job ID: $JOB_ID2"

# Kill it twice with proper state waiting
for k in {1..2}; do
    echo "[A2-P2] === Kill Round #$k ==="
    
    # Wait for job to be RUNNING with lease
    echo "[A2-P2] Waiting for job to be claimed (attempt $k)..."
    for i in {1..30}; do
        job_st=$(curl -sS "$API_URL/$JOB_ID2" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "unknown")
        if [[ "$job_st" == "running" && -f "$ROOT/runtime/job_leases/$JOB_ID2.json" ]]; then
            echo "[A2-P2] Job is RUNNING with lease"
            break
        fi
        sleep 1
    done
    
    # Get PID and kill
    if [[ -f "$ROOT/runtime/job_leases/$JOB_ID2.json" ]]; then
        pid=$(python3 -c "import json; print(json.load(open('$ROOT/runtime/job_leases/$JOB_ID2.json'))['meta']['pid'])")
        echo "[A2-P2] Killing worker PID $pid..."
        kill -9 "$pid"
    else
        echo "[A2-P2] ERROR: No lease file found"
        exit 5
    fi
    
    # Wait for reclamation to complete (lease file deleted)
    echo "[A2-P2] Waiting for reclamation..."
    for i in {1..30}; do
        if [[ ! -f "$ROOT/runtime/job_leases/$JOB_ID2.json" ]]; then
            echo "[A2-P2] Lease reclaimed"
            break
        fi
        sleep 1
    done
    
    # If this is kill #1, wait for job to be requeued
    if [[ $k -eq 1 ]]; then
        echo "[A2-P2] Waiting for job to be QUEUED..."
        for i in {1..20}; do
            job_st=$(curl -sS "$API_URL/$JOB_ID2" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "unknown")
            if [[ "$job_st" == "queued" ]]; then
                echo "[A2-P2] Job requeued for retry"
                break
            fi
            sleep 1
        done
    fi
done

echo "[A2-P2] Monitoring final failure..."
for i in {1..30}; do
    job_info=$(curl -sS "$API_URL/$JOB_ID2")
    st=$(echo "$job_info" | python3 -c "import sys, json; print(json.load(sys.stdin).get('status',''))")
    echo "[A2-P2] Status: $st (t=$i)"
    if [[ "$st" == "failed" ]]; then break; fi
    sleep 1
done

final_job=$(curl -sS "$API_URL/$JOB_ID2")
err=$(echo "$final_job" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error',{}).get('message',''))")
if [[ "$err" == "max_retries_exceeded_a2" ]]; then
    echo "[A2-P2] PASS: Max retries triggered correctly."
else
    echo "[A2-P2] FAIL: Expected max_retries_exceeded_a2, got '$err'"
    exit 3
fi

echo "[A2-P2] ALL TESTS PASSED ✅"
./runtime/launch_pool.zsh 5 & # Restore pool
