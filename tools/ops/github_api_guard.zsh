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
API_URL="https://api.github.com"

log() {
  printf "[%s] %s\n" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$1"
}

fail() {
  log "FAIL: $1"
  exit 1
}

is_nonneg_int() {
  [[ "$1" =~ '^[0-9]+$' ]]
}

check_auth() {
  gh auth status -h github.com >/dev/null 2>&1
}

check_https() {
  curl -sSf "$API_URL" >/dev/null 2>&1
}

check_rate_limit() {
  local remaining
  remaining="$(gh api rate_limit --jq '.resources.core.remaining' 2>/dev/null || true)"

  if [[ -z "$remaining" ]]; then
    return 1
  fi
  if ! [[ "$remaining" =~ '^[0-9]+$' ]]; then
    return 1
  fi

  log "Rate limit remaining: $remaining"
  (( remaining > 0 ))
}

attempt() {
  check_auth && check_https && check_rate_limit
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
