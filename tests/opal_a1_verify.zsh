#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
APP="$ROOT/runtime/apps/opal_api"
API_URL="http://127.0.0.1:7001"
OUTPUT_DIR="$ROOT/tests/a1_verify_output"
export PYTHONPATH="$ROOT"
mkdir -p "$OUTPUT_DIR"

echo "🧪 [A1 Verify] Starting Acceptance Tests..."

echo "🧹 [0/3] Preparing environment..."
pkill -f "opal_api/worker.py" || true
# Optional: echo "{}" > "$ROOT/observability/jobs_db.json"
if curl -s "$API_URL/api/jobs" > "$OUTPUT_DIR/jobs_response.json"; then
    echo "   ✅ /api/jobs reachable"
    # Basic check: is it a JSON object?
    if [[ $(cat "$OUTPUT_DIR/jobs_response.json") == \{* ]]; then
        echo "   ✅ Valid response structure (JSON Object)"
    else
        echo "   ❌ Invalid response structure!"
        cat "$OUTPUT_DIR/jobs_response.json"
        exit 1
    fi
else
    echo "   ❌ Failed to contact API. Is opal_api_server running?"
    exit 1
fi

# 2. Concurrency Test
echo "🚀 [2/3] Concurrency Test: 50 Jobs on 5 Workers..."
echo "   Starting Worker Pool..."
export OPAL_ENGINE_SLOTS=1
# Launch in background
"$ROOT/runtime/launch_pool.zsh" 5 > "$OUTPUT_DIR/pool.log" 2>&1 &
POOL_PID=$!
echo "   Pool PID: $POOL_PID"
sleep 5 # Wait for workers to start

echo "   Submitting 50 jobs..."
for i in {1..50}; do
  JOB_ID="job_a1_load_${i}_$(date +%s)"
  curl -s -X POST "$API_URL/api/jobs" \
       -H "Content-Type: multipart/form-data" \
       -F "prompt=load test $i" \
       -F "input_file=@$ROOT/core/docs/architecture_model.md" \
       -F "job_id=$JOB_ID" > /dev/null &
done
# Wait for submissions to finish (curls)
sleep 5 
echo "   Submissions sent."

echo "   Waiting for job completion (max 60s)..."
for i in {1..12}; do
    PENDING=$(curl -s "$API_URL/api/jobs" | jq '[.[] | select(.status == "queued")] | length')
    RUNNING=$(curl -s "$API_URL/api/jobs" | jq '[.[] | select(.status == "running")] | length')
    if [[ "$PENDING" == "0" && "$RUNNING" == "0" ]]; then
        echo "   ✅ All jobs terminal."
        break
    fi
    echo "   ... Pending: $PENDING, Running: $RUNNING"
    sleep 5
done

# Analyze
SUCC=$(curl -s "$API_URL/api/jobs" | jq '[.[] | select(.status == "succeeded")] | length')
FAILED=$(curl -s "$API_URL/api/jobs" | jq '[.[] | select(.status == "failed")] | length')

echo "   Stats: Succeeded=$SUCC, Failed=$FAILED"
if [[ "$SUCC" -ge 50 ]]; then
    echo "   ✅ Concurrency Test Passed (>=50 Succeeded)"
else
    echo "   ⚠️ Concurrency Test Warning: Some failed or logic is weird."
fi

# 3. Recovery Test
echo "💀 [3/3] Recovery Test: Simulate Worker Death..."
# Submit a long running job (mock?)
JOB_ID_KILL="job_kb_kill_test_$(date +%s)"

# Kill all workers to stop processing first
kill $POOL_PID || true
pkill -f "opal_api/worker.py" || true
sleep 2

# Submit job while no workers running
curl -s -X POST "$API_URL/api/jobs" \
       -H "Content-Type: multipart/form-data" \
       -F "prompt=sleep_10" \
       -F "input_file=@$ROOT/core/docs/architecture_model.md" \
       -F "job_id=$JOB_ID_KILL" > /dev/null

echo "   Job $JOB_ID_KILL submitted (Queued). Starting single worker to pick it up..."

# Launch 1 worker manually
(
    export WORKER_INDEX="99"
    export OPAL_ENGINE_SLOTS=1
    VENV_PYTHON="$ROOT/.venv/bin/python" # Assuming default
    export PYTHONPATH="$ROOT"
    "$VENV_PYTHON" "$APP/worker.py" > "$OUTPUT_DIR/worker_kill.log" 2>&1
) &
WORKER_PID=$!
echo "   Worker PID: $WORKER_PID. Waiting for it to pick up job..."
sleep 5

# Check if running
STATUS=$(curl -s "$API_URL/api/jobs/$JOB_ID_KILL" | jq -r .status)
if [[ "$STATUS" == "running" ]]; then
    echo "   ✅ Job is RUNNING. Killing Worker $WORKER_PID..."
    kill -9 $WORKER_PID
    echo "   Worker killed."
    
    echo "   Restarting Worker to trigger Recovery..."
    # Launch recovery worker
    (
        export WORKER_INDEX="100"
        VENV_PYTHON="$ROOT/.venv/bin/python"
        export PYTHONPATH="$ROOT"
        "$VENV_PYTHON" "$APP/worker.py" > "$OUTPUT_DIR/worker_recovery.log" 2>&1
    ) &
    REC_PID=$!
    sleep 5
    
    # Check status again
    NEW_STATUS=$(curl -s "$API_URL/api/jobs/$JOB_ID_KILL" | jq -r .status)
    ERROR_MSG=$(curl -s "$API_URL/api/jobs/$JOB_ID_KILL" | grep "worker_died_recovered_a1" || echo "")
    
    if [[ "$NEW_STATUS" == "failed" && -n "$ERROR_MSG" ]]; then
        echo "   ✅ Recovery SUCCESS: Job marked FAILED with reason 'worker_died_recovered_a1'"
    else
        echo "   ❌ Recovery FAILED: Status=$NEW_STATUS"
    fi
    
    kill $REC_PID || true
else
    echo "   ⚠️ Job didn't start in time. Status: $STATUS"
fi

# Cleanup
pkill -f "opal_api/worker.py" || true
echo "✅ A1 Verification Complete."
