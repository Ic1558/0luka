#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
cd "$ROOT"

ITERATIONS=${1:-3}
echo "=== Starting Stress Pass ($ITERATIONS iterations) ==="

check_guard() {
  system/tools/tk/tk_guard.zsh || {
    rc=$?
    if [[ $rc -ne 2 ]]; then
      echo "Critical incident detected! (RC: $rc)"
      exit 64
    fi
  }
}

for i in {1..$ITERATIONS}; do
  echo ""
  echo "--- Iteration $i ---"
  
  echo "Checking baseline..."
  check_guard

  echo "Running E2E Full Lifecycle..."
  python3 tests/test_e2e_full.py

  echo "Running Resilience (Targeted Kill)..."
  # Target uvicorn/opal_api specifically
  export PROCESS_MATCH="uvicorn.*opal_api_server"
  python3 tests/test_resilience.py

  echo "Verifying recovery..."
  sleep 2
  check_guard
done

echo ""
echo "=== STRESS PASS COMPLETE (All iterations passed) ==="
