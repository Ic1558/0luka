#!/usr/bin/env zsh
set -euo pipefail
IFS=$'\n\t'

# Shared header (defines OLUKA_ROOT + logging helpers)
source "${0:A:h}/../_shared/header_contract.zsh"

VERSION="0.1.0"

usage() {
  cat <<'USAGE'
codex.zsh (0luka) — knowledge/grep helper

Usage:
  codex.zsh list-skills
  codex.zsh query <term> [--scope skills|docs|all] [--max N]

Examples:
  codex.zsh list-skills
  codex.zsh query 0luka --scope skills --max 5
USAGE
}

cmd_list_skills() {
  # list skill.md under skills/*
  local skills_dir="${OLUKA_ROOT}/skills"
  [[ -d "${skills_dir}" ]] || { log_err "missing skills dir: ${skills_dir}"; return 2; }
  find "${skills_dir}" -mindepth 2 -maxdepth 2 -name "skill.md" -print | sed "s|^${OLUKA_ROOT}/||"
}

# safe grep: returns 0 with output, 1 no matches, >1 error
_safe_grep() {
  local term="$1"; shift
  local path="$1"; shift || true

  [[ -d "${path}" || -f "${path}" ]] || return 0

  set +e
  local out
  out="$(grep -RIn -- "${term}" "${path}" 2>/dev/null)"
  local st=$?
  set -e

  if [[ $st -eq 0 ]]; then
    print -r -- "${out}"
    return 0
  elif [[ $st -eq 1 ]]; then
    return 0
  else
    log_warn "grep error on ${path} (status ${st})"
    return 0
  fi
}

cmd_query() {
  local term="${1:-}"
  shift || true

  if [[ -z "${term}" ]]; then
    log_err "query requires <term>"
    usage
    return 64
  fi

  local scope="all"
  local max=20

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --scope)
        scope="${2:-}"
        shift 2
        ;;
      --max)
        max="${2:-}"
        shift 2
        ;;
      -h|--help)
        usage
        return 0
        ;;
      *)
        log_err "unknown flag: $1"
        usage
        return 64
        ;;
    esac
  done

  if [[ ! "${max}" =~ '^[0-9]+$' ]]; then
    log_err "--max must be integer"
    return 64
  fi

  local -a paths=()
  case "${scope}" in
    skills) paths=("${OLUKA_ROOT}/skills") ;;
    docs)   paths=("${OLUKA_ROOT}/docs") ;;
    all)    paths=("${OLUKA_ROOT}/skills" "${OLUKA_ROOT}/docs") ;;
    *)
      log_err "invalid --scope: ${scope} (use skills|docs|all)"
      return 64
      ;;
  esac

  log_info "[codex] query term='${term}' scope='${scope}' max=${max}"

  local -a lines=()
  local p
  for p in "${paths[@]}"; do
    local out
    out="$(_safe_grep "${term}" "${p}" || true)"
    if [[ -n "${out}" ]]; then
      # normalize paths to repo-relative
      out="$(print -r -- "${out}" | sed "s|^${OLUKA_ROOT}/||")"
      lines+=("${(f)out}")
    fi
  done

  if [[ ${#lines[@]} -eq 0 ]]; then
    log_warn "[codex] no results"
    return 0
  fi

  # print up to max lines
  print -r -- "${(F)lines[1,${max}]}"
}

main() {
  local cmd="${1:-help}"
  shift || true

  case "${cmd}" in
    list-skills) cmd_list_skills ;;
    query)       cmd_query "$@" ;;
    help|-h|--help) usage ;;
    *)
      log_err "unknown command: ${cmd} $*"
      usage
      return 64
      ;;
  esac
}

main "$@"
