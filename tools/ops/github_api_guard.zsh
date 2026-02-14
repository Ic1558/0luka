#!/usr/bin/env zsh
# github_api_guard.zsh
# Fail-closed GitHub transport preflight (deterministic, no side effects)

set -euo pipefail

MAX_RETRY="${MAX_RETRY:-3}"
SLEEP_SEC="${SLEEP_SEC:-2}"

log() {
  echo "[github-guard] $1"
}

fail() {
  log "FAIL: $1"
  exit 1
}

check_dns() {
  log "Checking DNS resolve for github.com"
  if ! command -v dig >/dev/null 2>&1; then
    log "DNS check failed: dig not available"
    return 1
  fi
  if ! dig +short github.com | grep -E '^[0-9]|:' >/dev/null; then
    log "DNS check failed: resolution failed"
    return 1
  fi
}

check_tcp() {
  log "Checking TCP connectivity to github.com:443"
  if ! command -v nc >/dev/null 2>&1; then
    log "TCP check failed: nc not available"
    return 1
  fi
  if ! nc -z -w 5 github.com 443 >/dev/null 2>&1; then
    log "TCP check failed: connect to 443 failed"
    return 1
  fi
}

check_https_api() {
  log "Checking HTTPS https://api.github.com"
  if ! command -v curl >/dev/null 2>&1; then
    log "HTTPS check failed: curl not available"
    return 1
  fi
  if ! curl -sf --connect-timeout 5 --max-time 10 https://api.github.com >/dev/null; then
    log "HTTPS check failed: GitHub API unreachable"
    return 1
  fi
}

check_gh_auth() {
  log "Checking gh authentication"
  if ! command -v gh >/dev/null 2>&1; then
    log "Auth check failed: gh not available"
    return 1
  fi
  if ! gh auth status >/dev/null 2>&1; then
    log "Auth check failed: gh not authenticated"
    return 1
  fi
}

check_rate_limit() {
  log "Checking GitHub rate limit"
  if ! command -v gh >/dev/null 2>&1; then
    log "Rate limit check failed: gh not available"
    return 1
  fi

  local remaining
  remaining="$(gh api rate_limit --jq '.resources.core.remaining' 2>/dev/null)" || {
    log "Rate limit check failed: cannot query rate_limit"
    return 1
  }

  if [[ -z "${remaining}" ]]; then
    log "Rate limit check failed: empty remaining value"
    return 1
  fi

  if (( remaining <= 0 )); then
    local reset_epoch
    reset_epoch="$(gh api rate_limit --jq '.resources.core.reset' 2>/dev/null)" || reset_epoch="unknown"
    log "Rate limit check failed: exhausted (reset epoch ${reset_epoch})"
    return 1
  fi

  log "Rate limit remaining: ${remaining}"
}

attempt() {
  check_dns && check_tcp && check_https_api && check_gh_auth && check_rate_limit
}

integer i
for (( i = 1; i <= MAX_RETRY; i++ )); do
  log "Attempt ${i}/${MAX_RETRY}"
  if attempt; then
    log "OK"
    exit 0
  fi
  if (( i < MAX_RETRY )); then
    log "Retry ${i}/${MAX_RETRY} failed, sleeping ${SLEEP_SEC}s..."
    sleep "${SLEEP_SEC}"
  fi
done

fail "GitHub transport layer not healthy after ${MAX_RETRY} attempts"
