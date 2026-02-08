#!/usr/bin/env zsh
# A2.1: Retry Policy & Idempotency Verification
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:7001}"
POST="$API_BASE/api/jobs"
LIST="$API_BASE/api/jobs"

ROOT="${ROOT:-$HOME/0luka}"
EVID_BASE="${EVID_BASE:-$HOME/opal_a2_evidence}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
EVID_DIR="$EVID_BASE/a2_1_${TS}"
mkdir -p "$EVID_DIR"

TIMEOUT_SECS="${TIMEOUT_SECS:-240}"
POLL_SECS="${POLL_SECS:-0.5}"

MAX_ATTEMPTS="${MAX_ATTEMPTS:-2}"
BACKOFF_EXPECT_SECS="${BACKOFF_EXPECT_SECS:-8}"

INPUT_FILE="${INPUT_FILE:-$ROOT/dummy_job.txt}"

echo "[A2.1] API_BASE=$API_BASE"
echo "[A2.1] POST=$POST"
echo "[A2.1] LIST=$LIST"
echo "[A2.1] EVID_DIR=$EVID_DIR"
echo "[A2.1] MAX_ATTEMPTS=$MAX_ATTEMPTS BACKOFF_EXPECT_SECS=$BACKOFF_EXPECT_SECS"
echo "[A2.1] INPUT_FILE=$INPUT_FILE"

# --- helpers ---
die(){ echo "[A2.1] FAIL: $*" | tee -a "$EVID_DIR/summary.txt"; exit 1; }

curl_json(){
  local url="$1"
  curl -sS "$url"
}

submit_job(){
  local prompt="$1"
  echo "dummy" > "$INPUT_FILE"
  curl -sS -X POST "$POST" \
    -F "prompt=$prompt" \
    -F "input_file=@$INPUT_FILE" \
    -F "metadata={\"engine\":\"mock_engine_v1\"}" \
    | tee "$EVID_DIR/submit_${prompt}.json"
}

job_status(){
  local job_id="$1"
  curl_json "$LIST/$job_id" | python3 - <<'PY'
import json,sys
j=json.load(sys.stdin)
print(j.get("status",""))
PY
}

wait_for_status(){
  local job_id="$1"
  local want="$2"
  local t0="$(date +%s)"
  while true; do
    local st="$(job_status "$job_id")"
    [[ "$st" == "$want" ]] && return 0
    local now="$(date +%s)"
    (( now - t0 > TIMEOUT_SECS )) && return 1
    sleep "$POLL_SECS"
  done
}

kill_worker_for_job(){
  local job_id="$1"
  # Find worker PID from lease file
  local lease_file="$ROOT/runtime/job_leases/${job_id}.json"
  if [[ ! -f "$lease_file" ]]; then
    die "No lease file found for job $job_id"
  fi
  
  local pid=$(python3 -c "import json; print(json.load(open('$lease_file'))['meta']['pid'])")
  echo "[A2.1] Killing worker PID $pid for job $job_id" | tee -a "$EVID_DIR/summary.txt"
  kill -9 "$pid" || true
}

attempt_file(){
  local job_id="$1"
  echo "$ROOT/runtime/job_attempts/${job_id}.json"
}

wait_for_attempt(){
  local job_id="$1"
  local want="$2"
  local t0="$(date +%s)"
  local f="$(attempt_file "$job_id")"
  while true; do
    if [[ -f "$f" ]]; then
      local a
      a="$(python3 -c "import json; print(json.load(open('$f')).get('attempts',0))" 2>/dev/null || echo 0)"
      [[ "$a" == "$want" ]] && return 0
    fi
    local now="$(date +%s)"
    (( now - t0 > TIMEOUT_SECS )) && return 1
    sleep "$POLL_SECS"
  done
}

# --- baseline parity snapshot ---
curl -sS "$LIST" > "$EVID_DIR/jobs_before.json" || die "failed to snapshot jobs_before"

# =========================
# Test #1: Retry success
# =========================
PROMPT1="SLEEP_TEST_20s_RETRY"
echo "[A2.1] Test#1 submit: $PROMPT1" | tee -a "$EVID_DIR/summary.txt"
submit_job "$PROMPT1" > "$EVID_DIR/submit1_body.json"

JOB1="$(python3 -c "import json; print(json.load(open('$EVID_DIR/submit1_body.json')).get('id',''))" || true)"
[[ -z "$JOB1" ]] && die "Test#1 submit did not return job id"

echo "[A2.1] Test#1 job=$JOB1" | tee -a "$EVID_DIR/summary.txt"
wait_for_status "$JOB1" "running" || die "Test#1 did not reach running"

kill_worker_for_job "$JOB1"

# wait reclaim -> attempt bump to 2 (and observe backoff window)
wait_for_attempt "$JOB1" "2" || die "Test#1 did not bump to attempt_2"
echo "[A2.1] Test#1 attempt_2 observed (backoff expected ~${BACKOFF_EXPECT_SECS}s)" | tee -a "$EVID_DIR/summary.txt"

wait_for_status "$JOB1" "succeeded" || die "Test#1 did not succeed after retry"

# Check output isolation
if [[ -d "$ROOT/runtime/opal_artifacts/$JOB1/attempt_1" && -d "$ROOT/runtime/opal_artifacts/$JOB1/attempt_2" ]]; then
  echo "[A2.1] Test#1 output isolation verified" | tee -a "$EVID_DIR/summary.txt"
else
  die "Test#1 output isolation failed"
fi

# =========================
# Test #2: Max retries exceeded
# =========================
PROMPT2="SLEEP_TEST_30s_MAX_RETRIES"
echo "[A2.1] Test#2 submit: $PROMPT2" | tee -a "$EVID_DIR/summary.txt"
submit_job "$PROMPT2" > "$EVID_DIR/submit2_body.json"

JOB2="$(python3 -c "import json; print(json.load(open('$EVID_DIR/submit2_body.json')).get('id',''))" || true)"
[[ -z "$JOB2" ]] && die "Test#2 submit did not return job id"

echo "[A2.1] Test#2 job=$JOB2" | tee -a "$EVID_DIR/summary.txt"

# kill #1
wait_for_status "$JOB2" "running" || die "Test#2 did not reach running (attempt_1)"
kill_worker_for_job "$JOB2"
wait_for_attempt "$JOB2" "2" || die "Test#2 did not bump to attempt_2"

# Wait for backoff + claim
sleep $(( BACKOFF_EXPECT_SECS + 2 ))

# kill #2
wait_for_status "$JOB2" "running" || die "Test#2 did not reach running (attempt_2)"
kill_worker_for_job "$JOB2"

# final: must fail with max retries
wait_for_status "$JOB2" "failed" || die "Test#2 did not end in failed"

# Check error message
ERROR_MSG=$(curl -sS "$LIST/$JOB2" | python3 -c "import json,sys; print(json.load(sys.stdin).get('error',{}).get('message',''))")
if [[ "$ERROR_MSG" == "max_retries_exceeded_a2" ]]; then
  echo "[A2.1] Test#2 error message verified: $ERROR_MSG" | tee -a "$EVID_DIR/summary.txt"
else
  die "Test#2 expected max_retries_exceeded_a2, got: $ERROR_MSG"
fi

# --- parity check ---
curl -sS "$LIST" > "$EVID_DIR/jobs_after.json" || die "failed to snapshot jobs_after"
python3 - "$EVID_DIR/jobs_before.json" "$EVID_DIR/jobs_after.json" > "$EVID_DIR/parity.txt" <<'PY'
import json,sys
b=json.load(open(sys.argv[1]))
a=json.load(open(sys.argv[2]))
def keys_of(x):
  if isinstance(x,list) and x: return sorted(x[0].keys())
  if isinstance(x,dict) and x:
    v=next(iter(x.values()))
    if isinstance(v,dict): return sorted(v.keys())
  return []
print("before_keys:", keys_of(b))
print("after_keys :", keys_of(a))
PY

echo "[A2.1] PASS ✅ Evidence: $EVID_DIR" | tee -a "$EVID_DIR/summary.txt"
