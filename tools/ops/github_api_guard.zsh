#!/usr/bin/env zsh
# github_api_guard.zsh
# Fail-closed GitHub transport + auth + rate-limit guard.
# Usage:
#   ./tools/ops/github_api_guard.zsh
#   TIME_BUDGET_SEC=120 ./tools/ops/github_api_guard.zsh

set -euo pipefail
export LC_ALL=C

TIME_BUDGET_SEC="${TIME_BUDGET_SEC:-90}"
INITIAL_BACKOFF_SEC="${INITIAL_BACKOFF_SEC:-2}"
MAX_BACKOFF_SEC="${MAX_BACKOFF_SEC:-15}"

log() {
  printf "[%s] %s\n" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$1"
}

fail() {
  log "FAIL: $1"
  exit 1
}

is_nonneg_int() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

# --- Deterministic IPv4-only Probes ---

auth_token() {
  # gh auth token is local-only (keychain) and should not perform network.
  gh auth token 2>/dev/null || true
}

check_https_api() {
  # GitHub API reachability over IPv4-only path.
  local code
  code="$(curl -4 -sS --max-time 8 -o /dev/null -w "%{http_code}" https://api.github.com || echo "000")"
  if [[ "$code" != "200" ]]; then
    log "FAIL: GitHub API not healthy over IPv4 (http=$code)"
    return 1
  fi
  return 0
}

check_auth() {
  # Validate token by calling /user with curl -4.
  local tok
  tok="$(auth_token)"
  if [[ -z "$tok" ]]; then
    log "FAIL: missing GH auth token (gh auth token returned empty)"
    return 1
  fi
  local code
  code="$(curl -4 -sS --max-time 8 -H "Authorization: Bearer $tok" -o /dev/null -w "%{http_code}" https://api.github.com/user || echo "000")"
  if [[ "$code" != "200" ]]; then
    log "FAIL: auth invalid via IPv4 curl (http=$code)"
    return 1
  fi
  return 0
}

check_rate_limit() {
  local tok
  tok="$(auth_token)"
  if [[ -z "$tok" ]]; then
    log "FAIL: missing GH auth token (cannot check rate limit)"
    return 1
  fi
  local remaining
  remaining="$(curl -4 -sS --max-time 8 -H "Authorization: Bearer $tok" https://api.github.com/rate_limit \
    | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["resources"]["core"]["remaining"])' 2>/dev/null || echo "")"
  
  if [[ -z "$remaining" ]]; then
    log "FAIL: rate limit parse failed"
    return 1
  fi
  
  if ! [[ "$remaining" =~ ^[0-9]+$ ]]; then
    log "FAIL: rate limit value invalid ($remaining)"
    return 1
  fi

  log "Rate limit remaining: $remaining"
  (( remaining > 0 ))
}

attempt() {
  check_https_api && check_auth && check_rate_limit
}

main() {
  is_nonneg_int "$TIME_BUDGET_SEC" || fail "TIME_BUDGET_SEC must be a non-negative integer"
  is_nonneg_int "$INITIAL_BACKOFF_SEC" || fail "INITIAL_BACKOFF_SEC must be a non-negative integer"
  is_nonneg_int "$MAX_BACKOFF_SEC" || fail "MAX_BACKOFF_SEC must be a non-negative integer"

  local start_ts now elapsed backoff attempt_no
  start_ts=$(date +%s)
  backoff=$INITIAL_BACKOFF_SEC
  attempt_no=1

  while true; do
    now=$(date +%s)
    elapsed=$(( now - start_ts ))

    if (( elapsed > TIME_BUDGET_SEC )); then
      fail "GitHub transport layer not healthy within ${TIME_BUDGET_SEC}s budget"
    fi

    log "Attempt ${attempt_no} (elapsed=${elapsed}s/${TIME_BUDGET_SEC}s)"
    if attempt; then
      log "OK"
      return 0
    fi

    if (( elapsed >= TIME_BUDGET_SEC )); then
      fail "GitHub transport layer not healthy within ${TIME_BUDGET_SEC}s budget"
    fi

    log "Retrying in ${backoff}s"
    sleep "$backoff"

    if (( backoff < MAX_BACKOFF_SEC )); then
      backoff=$(( backoff * 2 ))
      if (( backoff > MAX_BACKOFF_SEC )); then
        backoff=$MAX_BACKOFF_SEC
      fi
    fi

    attempt_no=$(( attempt_no + 1 ))
  done
}

main
