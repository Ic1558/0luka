#!/usr/bin/env zsh
# github_api_guard.zsh
# Fail-closed GitHub transport + auth + rate-limit guard

set -euo pipefail
export LC_ALL=C

MAX_RETRY="${MAX_RETRY:-3}"
SLEEP_SEC="${SLEEP_SEC:-2}"
API_URL="https://api.github.com"

log() {
  printf "[%s] %s\n" "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$1"
}

fail() {
  log "FAIL: $1"
  exit 1
}

check_auth() {
  gh auth status -h github.com >/dev/null 2>&1 || return 1
}

check_https() {
  curl -sSf "$API_URL" >/dev/null 2>&1 || return 1
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

  if (( remaining <= 0 )); then
    return 1
  fi
}

attempt() {
  check_auth && check_https && check_rate_limit
}

main() {
  local i=1
  while (( i <= MAX_RETRY )); do
    log "Attempt ${i}/${MAX_RETRY}"
    if attempt; then
      log "OK"
      return 0
    fi
    (( i++ ))
    if (( i <= MAX_RETRY )); then
      sleep "$SLEEP_SEC"
    fi
  done
  fail "GitHub transport layer not healthy after $MAX_RETRY attempts"
}

main
