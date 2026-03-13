#!/usr/bin/env zsh
set -euo pipefail

FAIL=0
WARN=0

ok() {
  echo "OK: $1"
}

warn() {
  echo "WARN: $1"
  WARN=$((WARN + 1))
}

fail() {
  echo "FAIL: $1"
  FAIL=1
}

REPO="/Users/icmini/0luka/repos/option"
VENV="$REPO/venv/bin/python3"
DOTENVX="/opt/homebrew/bin/dotenvx"
WRAPPER="/Users/icmini/0luka/tools/ops/antigravity_controltower_wrapper.zsh"
PLIST="/Users/icmini/0luka/docs/architecture/drafts/com.antigravity.controltower.plist"
LOGDIR="$REPO/artifacts"

echo "== runtime doctor (read-only) =="
echo

if [[ -d "$REPO" ]]; then
  ok "repo exists: $REPO"
else
  fail "repo missing: $REPO"
fi

if [[ -x "$VENV" ]]; then
  ok "venv python exists: $VENV"
else
  fail "venv python missing or not executable: $VENV"
fi

if [[ -x "$DOTENVX" ]]; then
  ok "dotenvx exists: $DOTENVX"
else
  fail "dotenvx missing or not executable: $DOTENVX"
fi

if [[ -f "$WRAPPER" ]]; then
  ok "wrapper file exists: $WRAPPER"
else
  fail "wrapper file missing: $WRAPPER"
fi

if [[ -f "$PLIST" ]]; then
  ok "plist draft exists: $PLIST"
else
  fail "plist draft missing: $PLIST"
fi

if [[ -d "$LOGDIR" ]]; then
  ok "log dir exists: $LOGDIR"
else
  warn "log dir missing (wrapper will create at runtime): $LOGDIR"
fi

if command -v plutil >/dev/null 2>&1; then
  if plutil -lint "$PLIST" >/dev/null 2>&1; then
    ok "plist validates with plutil"
  else
    fail "plist failed plutil -lint"
  fi
else
  warn "plutil not available; cannot lint plist"
fi

if command -v launchctl >/dev/null 2>&1; then
  if launchctl list | grep -q com.antigravity.controltower; then
    ok "launchd label present: com.antigravity.controltower"
  else
    warn "launchd label not found: com.antigravity.controltower"
  fi
else
  warn "launchctl not available"
fi

if command -v pm2 >/dev/null 2>&1; then
  if pm2 list | grep -q Antigravity-HQ; then
    ok "PM2 app present: Antigravity-HQ"
  else
    warn "PM2 app not found: Antigravity-HQ"
  fi
else
  warn "pm2 not available"
fi

if command -v lsof >/dev/null 2>&1; then
  if lsof -nP -iTCP:8089 -sTCP:LISTEN >/dev/null 2>&1; then
    ok "port 8089 has a listener"
    lsof -nP -iTCP:8089 -sTCP:LISTEN
  else
    warn "port 8089 has no listener"
  fi
else
  warn "lsof not available"
fi

echo
if [[ $FAIL -eq 1 ]]; then
  echo "RESULT: FAIL (see messages above)"
  exit 1
fi

echo "RESULT: OK (warnings=$WARN)"
exit 0
