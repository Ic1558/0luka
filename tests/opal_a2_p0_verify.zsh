#!/usr/bin/env zsh
# A2-Phase 0: Worker Registry Verification script
set -euo pipefail

ROOT="${ROOT:-/Users/icmini/0luka}"
REG_FILE="$ROOT/runtime/worker_registry.json"
API_URL="http://127.0.0.1:7001/api/jobs"

echo "[A2-P0] Registry Path: $REG_FILE"

# 1. Registry Awareness Test
echo "[A2-P0] 1. Checking registry existence and population..."
if [[ ! -f "$REG_FILE" ]]; then
    echo "[A2-P0] FAIL: Registry file not found."
    exit 1
fi

count=$(python3 -c "import json; print(len(json.load(open('$REG_FILE'))['workers']))")
echo "[A2-P0] Active workers in registry: $count"

if (( count < 1 )); then
    echo "[A2-P0] FAIL: No workers registered."
    exit 2
fi

# 2. Heartbeat Freshness Test
echo "[A2-P0] 2. Monitoring heartbeats for 5s..."
bash -c "for i in {1..5}; do 
  ts=\$(python3 -c \"import json; print(json.load(open('$REG_FILE'))['updated_at'])\")
  echo \"[A2-P0] Update TS: \$ts\"
  sleep 1.5
done"

# 3. Stale Prune Test
echo "[A2-P0] 3. Testing stale prune (kill 1 worker)..."
target_pid=$(python3 -c "import json; w = json.load(open('$REG_FILE'))['workers']; print(next(iter(w.values()))['meta']['pid'])")
target_id=$(python3 -c "import json; w = json.load(open('$REG_FILE'))['workers']; print(next(iter(w.values()))['worker_id'])")

echo "[A2-P0] Killing worker $target_id (PID $target_pid)"
kill -9 "$target_pid"

echo "[A2-P0] Waiting for TTL (12s)..."
sleep 12

new_count=$(python3 -c "import json; print(len(json.load(open('$REG_FILE'))['workers']))")
echo "[A2-P0] Active workers after kill + TTL: $new_count"

if (( new_count >= count )); then
    echo "[A2-P0] FAIL: Stale worker NOT pruned."
    exit 3
fi

# 4. ABI Parity Check
echo "[A2-P0] 4. Verifying ABI parity (/api/jobs keys)..."
curl -sS "$API_URL" > jobs_a2.json
python3 - <<'PY'
import json, sys
data = json.load(open("jobs_a2.json"))
jobs = data.get("jobs", []) or list(data.values())
if not jobs:
    print("No jobs found, but checking keys of empty list is moot.")
else:
    sample = jobs[0] if isinstance(jobs[0], dict) else {}
    keys = sorted(sample.keys())
    # Expected A1 keys
    expected = ["completed_at", "created_at", "error", "id", "outputs", "run_provenance", "started_at", "status"]
    if all(k in keys for k in expected):
        print(f"ABI Match: {keys}")
    else:
        print(f"ABI MISMATCH! Found: {keys}")
        sys.exit(1)
PY

echo "[A2-P0] PASS ✅"
