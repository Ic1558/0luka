#!/usr/bin/env bash
# preflight_github.zsh — Network gate for GitHub API operations.
# Run BEFORE gh commands. Exits on first failure.

set -euo pipefail

check_dns() {
  printf "[preflight] DNS check: ping github.com ... "
  if ping -c 1 github.com >/dev/null 2>&1; then
    echo "OK"
  else
    echo "FAIL"
    echo "[preflight] ERROR: DNS resolution for github.com failed" >&2
    exit 1
  fi
}

check_api() {
  printf "[preflight] API check: curl https://api.github.com ... "
  if curl -sf --max-time 10 https://api.github.com >/dev/null 2>&1; then
    echo "OK"
  else
    echo "FAIL"
    echo "[preflight] ERROR: cannot reach https://api.github.com" >&2
    exit 1
  fi
}

check_auth() {
  printf "[preflight] Auth check: gh auth status ... "
  if gh auth status >/dev/null 2>&1; then
    echo "OK"
  else
    echo "FAIL"
    echo "[preflight] ERROR: gh auth status failed (token expired or not logged in)" >&2
    exit 1
  fi
}

check_dns
check_api
check_auth

echo "[preflight] OK"
