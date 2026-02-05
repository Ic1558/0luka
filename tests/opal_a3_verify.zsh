#!/usr/bin/env zsh
set -euo pipefail

ROOT=$(pwd)
export PYTHONPATH="$ROOT"
export OPAL_TELEMETRY_ENABLED=1
export OPAL_WORKER_TTL=5
export OPAL_REGISTRY_PRUNE_EVERY_SECS=3
export OPAL_HEARTBEAT_INTERVAL=3  # Increased to reduce lock contention

echo "[A3] Starting Verification: Control Plane & Hygiene"

# Cleanup
echo "[A3] Cleanup..."
pkill -f "opal_api_server" || true
pkill -f "worker.py" || true
rm -f runtime/worker_registry.json runtime/worker_registry.json.lock

# 1. Start API Server
echo "[A3] Starting API Server..."
PYTHON_EXEC=".venv/bin/python3"
if [[ ! -x "$PYTHON_EXEC" ]]; then PYTHON_EXEC="python3"; fi

$PYTHON_EXEC runtime/apps/opal_api/opal_api_server.py > runtime/logs/api_server.log 2>&1 &
API_PID=$!
sleep 5 # Wait longer for startup
if ! ps -p $API_PID > /dev/null; then
  echo "❌ API Server failed to start"
  cat runtime/logs/api_server.log
  exit 1
fi

# 2. Start Workers (N=3)
echo "[A3] Starting Worker Pool (N=3)..."
./runtime/launch_pool.zsh 3 &
POOL_PID=$!
echo "Waiting 6s for heartbeats..."
sleep 6

# 3. Test /api/nodes
echo "[A3] Testing /api/nodes..."
curl -v --connect-timeout 5 --max-time 5 http://127.0.0.1:7001/api/nodes > nodes.json 2> curl_err.log || true
if [[ ! -s nodes.json ]]; then
  echo "❌ curl failed. Error log:"
  cat curl_err.log
  cat runtime/logs/api_server.log
  exit 1
fi
NODES_JSON=$(cat nodes.json)
echo "Response: $NODES_JSON"

HOST_COUNT=$(echo "$NODES_JSON" | jq '.nodes | length')
WORKER_COUNT=$(echo "$NODES_JSON" | jq '.nodes[0].worker_count')

if [[ "$HOST_COUNT" -ge 1 && "$WORKER_COUNT" -eq 3 ]]; then
  echo "✅ /api/nodes Correct (1 Host, 3 Workers)"
else
  echo "❌ FAIL: Expected 1 Host, 3 Workers. Got Host=$HOST_COUNT, Worker=$WORKER_COUNT"
  exit 1
fi

# 4. Test Hygiene (Pruning)
echo "[A3] Testing Hygiene (Pruning)..."
# Kill all workers
pkill -f "worker.py"
echo "Workers killed. Waiting 6s for TTL(5s) to expire..."
sleep 6

# Start 1 new worker to trigger prune
echo "[A3] Starting 1 new worker to trigger prune..."
./runtime/launch_pool.zsh 1 &
NEW_POOL_PID=$!
echo "Waiting 5s for Prune Interval(3s) + Heartbeat..."
sleep 5

WORKERS_JSON=$(curl -s http://127.0.0.1:7001/api/workers)
COUNT=$(echo "$WORKERS_JSON" | jq 'length')

# Should be 1 (the new one). Old 3 should be gone.
if [[ "$COUNT" -eq 1 ]]; then
  echo "✅ Hygiene Verified: Stale workers pruned. Count=1"
else
  echo "❌ FAIL: Expected 1 worker, found $COUNT"
  echo "$WORKERS_JSON"
  exit 1
fi

# Cleanup
kill $API_PID
pkill -f "worker.py"

echo "[A3] ✅ All Systems Go (Control Plane + Hygiene Verified)"
exit 0
