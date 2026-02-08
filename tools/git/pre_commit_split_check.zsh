#!/bin/zsh
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  zsh tools/git/pre_commit_split_check.zsh --pattern '<regex>' [--branch <name>] [--file <paths.txt>] [--label <name>]

Behavior:
  - If --file is provided, validates those paths (one path per line).
  - Else validates staged paths from: git diff --cached --name-only
  - If --branch is provided, runs inside that branch and returns to original branch.
EOF
}

PATTERN=""
BRANCH=""
FILE=""
LABEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pattern) PATTERN="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --file) FILE="$2"; shift 2 ;;
    --label) LABEL="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ -z "$PATTERN" ]]; then
  echo "ERROR: --pattern is required"
  usage
  exit 2
fi

orig_branch="$(git rev-parse --abbrev-ref HEAD)"
cleanup() {
  if [[ -n "$BRANCH" && "$orig_branch" != "$(git rev-parse --abbrev-ref HEAD)" ]]; then
    git switch "$orig_branch" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ -n "$BRANCH" ]]; then
  git switch "$BRANCH" >/dev/null
fi

if [[ -z "$LABEL" ]]; then
  LABEL="${BRANCH:-$(git rev-parse --abbrev-ref HEAD)}"
fi

echo "=== $LABEL ==="

paths=""
if [[ -n "$FILE" ]]; then
  if [[ ! -f "$FILE" ]]; then
    echo "ERROR: file not found: $FILE"
    exit 2
  fi
  paths="$(sed '/^\s*$/d' "$FILE" | sort -u)"
  echo "-- source file: $FILE"
else
  paths="$(git diff --cached --name-only | sed '/^\s*$/d' | sort -u)"
  echo "-- source: staged (git diff --cached --name-only)"
  echo "-- cached stat --"
  git diff --cached --stat || true
fi

if [[ -z "$paths" ]]; then
  echo "NOTE: no paths to validate"
  exit 0
fi

echo "-- paths --"
printf '%s\n' "$paths"

echo "-- scope check --"
if printf '%s\n' "$paths" | rg -v "$PATTERN"; then
  echo "UNEXPECTED FILES"
  exit 1
else
  echo "OK"
fi
