#!/usr/bin/env zsh
# preflight_github.zsh — Network gate for GitHub API operations
# Run BEFORE any gh pr / gh merge / gh api call to verify connectivity.
# Exit 0 = all clear, Exit 1 = network or auth problem.

set -euo pipefail

FAIL=0

# ── 1. DNS resolution ──────────────────────────────────────────────
printf "[preflight] DNS check: ping github.com ... "
if ping -c 1 -W 5 github.com >/dev/null 2>&1; then
  echo "OK"
else
  echo "FAIL"
  echo "[preflight] ERROR: DNS resolution for github.com failed" >&2
  FAIL=1
fi

# ── 2. API reachability ────────────────────────────────────────────
printf "[preflight] API check: curl api.github.com ... "
if curl -sf --max-time 10 https://api.github.com >/dev/null 2>&1; then
  echo "OK"
else
  echo "FAIL"
  echo "[preflight] ERROR: api.github.com unreachable or returned error" >&2
  FAIL=1
fi

# ── 3. gh auth ─────────────────────────────────────────────────────
printf "[preflight] Auth check: gh auth status ... "
if gh auth status >/dev/null 2>&1; then
  echo "OK"
else
  echo "FAIL"
  echo "[preflight] ERROR: gh auth status failed — token expired or not logged in" >&2
  FAIL=1
fi

# ── Result ─────────────────────────────────────────────────────────
if (( FAIL )); then
  echo "[preflight] BLOCKED — fix the above before running GitHub operations" >&2
  exit 1
fi

echo "[preflight] OK"
exit 0
