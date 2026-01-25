#!/usr/bin/env zsh
set -euo pipefail

# --- BASE: repo root auto-detect (0luka) ---
SCRIPT_DIR="$(cd -- "$(dirname -- "${0:A}")" && pwd)"
BASE="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
# ------------------------------------------

need_cmd() { command -v "$1" >/dev/null 2>&1; }

say() { print -r -- "$*"; }
die() { print -r -- "ERROR: $*" >&2; exit 1; }

[[ -d "$BASE" ]] || die "Base not found: $BASE"

RG_BIN=""
if need_cmd rg; then
  RG_BIN="rg"
elif need_cmd grep; then
  RG_BIN="grep"
else
  die "Need rg or grep"
fi

# Illegal paths (hard fail if referenced by processes/logs/plists/code)
typeset -a ILLEGAL=(
  "$BASE/g/tools/"
  "$BASE/g/reports/"
  "$BASE/g/telemetry/"
  "$BASE/g/logs/"
  "$BASE/g/core_history/"
)

# Runtime output must be confined here (informational guard; not a hard fail by itself)
typeset -a RUNTIME_OK=(
  "$BASE/observability/"
)

# Scan targets
typeset -a SCAN_DIRS=(
  "$BASE"
  "$HOME/Library/LaunchAgents"
  "/Library/LaunchAgents"
  "/Library/LaunchDaemons"
)

typeset -i fail=0

scan_text() {
  local label="$1"; shift
  local needle="$1"; shift
  local dir="$1"; shift

  [[ -d "$dir" ]] || return 0

  if [[ "$RG_BIN" == "rg" ]]; then
    if rg -n --hidden --no-ignore-vcs --follow --fixed-strings -- "$needle" "$dir" >/dev/null 2>&1; then
      say ""
      say "=== VIOLATION: $label"
      say "needle: $needle"
      say "where : $dir"
      rg -n --hidden --no-ignore-vcs --follow --fixed-strings -- "$needle" "$dir" | sed -n '1,120p'
      fail=1
    fi
  else
    if grep -RIn -- "$needle" "$dir" >/dev/null 2>&1; then
      say ""
      say "=== VIOLATION: $label"
      say "needle: $needle"
      say "where : $dir"
      grep -RIn -- "$needle" "$dir" | sed -n '1,120p'
      fail=1
    fi
  fi
}

scan_processes() {
  local needle="$1"
  if ps axww -o pid=,command= | grep -F -- "$needle" | grep -v -F -- "enforce_runtime_hygiene.zsh" | grep -v grep >/dev/null 2>&1; then
    say ""
    say "=== VIOLATION: running process references illegal path"
    say "needle: $needle"
    ps axww -o pid=,command= | grep -F -- "$needle" | grep -v -F -- "enforce_runtime_hygiene.zsh" | grep -v grep | sed -n '1,80p'
    fail=1
  fi
}

check_git_hygiene() {
  [[ -d "$BASE/.git" ]] || return 0
  local st
  st="$(cd "$BASE" && git status --porcelain || true)"
  if [[ -n "$st" ]]; then
    say ""
    say "=== WARNING: git status not clean in $BASE"
    say "$st" | sed -n '1,200p'
    # Not hard-fail by default, because ignores may not be applied yet.
  fi
}

check_gitignore_rules() {
  local gi="$BASE/.gitignore"
  [[ -f "$gi" ]] || { say ""; say "=== WARNING: missing .gitignore at $gi"; return 0; }

  local -a req=(
    "observability/**"
    "runtime/**"
    "g/**"
    "artifacts/**"
    ".DS_Store"
    ".claude"
  )

  local r
  for r in "${req[@]}"; do
    if ! grep -Fqx -- "$r" "$gi" >/dev/null 2>&1; then
      say ""
      say "=== WARNING: .gitignore missing exact line: $r"
      say "file: $gi"
    fi
  done
}

main() {
  say "enforce_runtime_hygiene"
  say "BASE: $BASE"
  say ""

  local p d
  for p in "${ILLEGAL[@]}"; do
    # Scan logs/plists/code for path references
    for d in "${SCAN_DIRS[@]}"; do
      scan_text "text-scan" "$p" "$d"
    done
    # Scan running processes
    scan_processes "$p"
  done

  check_gitignore_rules
  check_git_hygiene

  if (( fail )); then
    say ""
    die "FAILED: illegal path references detected"
  fi

  say "OK: no illegal path references detected"
}

main "$@"
