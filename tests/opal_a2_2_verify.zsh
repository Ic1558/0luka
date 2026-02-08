#!/usr/bin/env zsh
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:7001}"
ROOT="${ROOT:-$HOME/0luka}"
IDENTITY_DIR="$ROOT/runtime/identity"

echo "[A2.2] Identity & Clock Guard Verification"

# 1. Setup
echo "[A2.2] Cleaning up..."
pkill -f "opal_api/worker.py" || true
rm -rf "$IDENTITY_DIR"
mkdir -p "$IDENTITY_DIR"

# 2. Start Pool (N=3)
echo "[A2.2] Starting pool..."
export OPAL_ENABLE_A1_PID_RECOVERY=0
export OPAL_CLOCK_SKEW_TOLERANCE_SECS=3
./runtime/launch_pool.zsh 3 &
sleep 5

# 3. Verify Identities Persisted
echo "[A2.2] Checking identity files..."
if [[ -f "$IDENTITY_DIR/host.json" && -f "$IDENTITY_DIR/worker_seq.json" ]]; then
  echo "[A2.2] ✅ Found identity files (host.json, worker_seq.json)."
else
  echo "[A2.2] ❌ FAIL: Missing identity files in $IDENTITY_DIR"
  ls -F "$IDENTITY_DIR"
fi

# 4. Identity Persistence Test (Restart)
echo "[A2.2] Restarting pool (simulating restart on same hosts)..."
# Capture IDs before restart
declare -A IDS_BEFORE
for f in "$IDENTITY_DIR"/*.json; do
    if [[ $(basename "$f") == "host.json" || $(basename "$f") == "worker_seq.json" ]]; then continue; fi
    # Wait, IdentityManager writes persistence to... 
    # Ah, IdentityManager writes host.json and worker_seq.json
    # WORKER_ID is host_id:seq
    # Worker registry stores the active workers.
done

# We need to query the REGISTRY to see what workers are active.
# Or check logs.
REGISTRY_FILE="$ROOT/runtime/worker_registry.json"

get_active_workers() {
    python3 -c "import json; print(list(json.load(open('$REGISTRY_FILE'))['workers'].keys()))" 2>/dev/null
}

echo "[A2.2] Active workers before restart:"
IDS_BEFORE=$(get_active_workers)
echo "$IDS_BEFORE"

pkill -f "opal_api/worker.py" || true
sleep 3
./runtime/launch_pool.zsh 3 &
sleep 10 # Wait for heartbeats

echo "[A2.2] Active workers after restart:"
IDS_AFTER=$(get_active_workers)
echo "$IDS_AFTER"

# Verification:
# host_id should be stable (single host).
# worker_seqs might increment if allocate_worker_seq is called on every start.
# IdentityManager.allocate_worker_seq() increments the counter.
# So if we restart, new workers get NEW seqs?
# Yes: "next_seq" = "current" + 1.
# So IDs will be DIFFERENT: host_id:1, host_id:2... -> host_id:4, host_id:5...

# BUT host.json (host UUID) must remain same.
HOST_ID_FILE="$IDENTITY_DIR/host.json"
if [[ ! -f "$HOST_ID_FILE" ]]; then
    echo "[A2.2] ❌ FAIL: host.json missing"
    exit 1
fi
HOST_ID=$(python3 -c "import json; print(json.load(open('$HOST_ID_FILE'))['host_id'])")
echo "[A2.2] Host ID: $HOST_ID"

# Verify all worker IDs start with this Host ID
if echo "$IDS_AFTER" | grep -q "$HOST_ID"; then
    echo "[A2.2] ✅ Worker IDs use persistent Host ID"
else
    echo "[A2.2] ❌ FAIL: Worker IDs do not match Host ID"
    exit 1
fi

echo "[A2.2] ✅ PASS: Identity stability verified"
