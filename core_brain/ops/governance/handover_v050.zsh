#!/usr/bin/env zsh
# handover_v041.zsh
# The "Golden Script" to Start, Verify, and Stop the v0.4.1 Judicial Daemon.
# Handover-Grade: PID-based control, Log Assertion, Clean Exit.

ROOT="$HOME/0luka"
OPS_DIR="$ROOT/ops/governance"
LOG_FILE="/tmp/gate_runnerd_v050.log"
PID_FILE="/tmp/gate_runnerd.pid"

cd "$OPS_DIR" || { echo "❌ Cannot find ops dir"; exit 1; }

echo "--- 1. PRE-FLIGHT CLEANUP ---"
if [[ -f "$PID_FILE" ]]; then
    OLD_PID=$(cat "$PID_FILE")
    kill "$OLD_PID" 2>/dev/null || true
    echo "   Cleaned up old PID $OLD_PID"
fi
pkill -f gate_runnerd.py || true # Safety net
rm -f "$ROOT/runtime/sock/gate_runner.sock"
: > "$LOG_FILE" # Truncate log


# Capture start timestamp
START_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "--- 2. STARTING JUDICIAL DAEMON v0.5.0 (Start: $START_TIME) ---"
nohup python3 gate_runnerd.py > "$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"
echo "   Daemon started with PID $PID. Logs at $LOG_FILE"
sleep 2

# Check if alive
if ps -p $PID > /dev/null; then
    echo "   ✅ Daemon is ALIVE."
else
    echo "   ❌ Daemon CRASHED immediatey."
    cat "$LOG_FILE"
    exit 1
fi

echo "--- 3. RUNNING VERIFICATION (verify_v050.py) ---"
python3 verify_v050.py
RET=$?

echo "--- 4. LOG AUDIT (JSONDecodeError Check) ---"
if grep -q "JSONDecodeError" "$LOG_FILE"; then
    echo "   ❌ FAIL: Log contains JSONDecodeError (Noise not silenced)"
    RET=1
else
    echo "   ✅ PASS: Log is clean of JSONDecodeError"
fi

echo "--- 5. STOPPING DAEMON ---"
kill $PID
wait $PID 2>/dev/null
rm -f "$PID_FILE"
END_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "   ✅ Daemon STOPPED (End: $END_TIME)."

if [ $RET -eq 0 ]; then
    echo "\n🏆 HANDOVER VERIFICATION PASSED."
    echo "Certification Window: $START_TIME <-> $END_TIME"
    exit 0
else
    echo "\n❌ HANDOVER VERIFICATION FAILED."
    exit 1
fi
