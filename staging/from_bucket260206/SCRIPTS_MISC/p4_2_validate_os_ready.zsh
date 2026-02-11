#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
cd "$ROOT"

echo "== Phase 4.2 Validate (Resilience + Hygiene) =="
echo "ROOT=$ROOT"
echo

# ---------- A) Hygiene / Caller Audit ----------
echo "== A) Caller audit (quick) =="
echo "-- handoff entrypoint exists?"
test -f "$ROOT/observability/artifacts/handoff_latest.json"
ls -la "$ROOT/observability/artifacts/handoff_latest.json"
echo

echo "-- reject legacy handoff paths (informational; should be empty or legacy-only) ..."
rg -n 'observability/reports/handoff_latest\.json|artifacts/handoff_latest\.json' . \
  -g'*.py' -g'*.zsh' -S || true
echo

echo "-- reject save_now legacy outdir (should be 0 hits now) ..."
rg -n 'observability/artifacts/save_now' . -g'*.py' -g'*.zsh' -S || true
echo

echo "== git status (baseline) =="
git status --porcelain | sed -n '1,200p'
echo

# ---------- B) Resilience ----------
echo "== B) Resilience =="
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:7001/health}"

echo "-- health check: $HEALTH_URL"
if ! curl -fsS "$HEALTH_URL" >/dev/null; then
  echo "FAIL: health endpoint not reachable: $HEALTH_URL"
  echo "Hint: confirm which service should own :7001 and ensure it is persistent (launchd)."
  exit 2
fi
echo "OK: health reachable"
echo

echo "-- find PID listening on :7001"
PID="$(lsof -nP -iTCP:7001 -sTCP:LISTEN 2>/dev/null | awk 'NR==2{print $2}' || true)"
if [[ -z "${PID}" ]]; then
  echo "FAIL: no PID is listening on :7001"
  exit 3
fi
echo "PID=$PID"
echo

echo "-- kill PID and wait for restart"
kill "$PID" || true
sleep 2

# wait up to ~12s for restart
ok=0
for i in {1..12}; do
  if curl -fsS "$HEALTH_URL" >/dev/null; then
    ok=1
    break
  fi
  sleep 1
done

if [[ "$ok" -ne 1 ]]; then
  echo "FAIL: service did not recover within 12s"
  echo "Check launchd/plist or runner supervising the service."
  exit 4
fi
echo "OK: service recovered"
echo

echo "-- run resilience test (if present)"
if [[ -f "$ROOT/tests/test_resilience.py" ]]; then
  python3 "$ROOT/tests/test_resilience.py"
  echo "OK: tests/test_resilience.py PASS"
else
  echo "SKIP: tests/test_resilience.py not found"
fi

echo
echo "== Phase 4.2 RESULT: PASS (Resilience + Hygiene checks executed) =="
