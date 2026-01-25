#!/usr/bin/env zsh
source "${0:A:h:h}/_shared/header_contract.zsh"

AGENT="antigravity"
VERSION="0.1.0"

ag_state_dir() { print -r -- "${OLUKA_STATE_DIR}/antigravity"; }
ag_pid_dir() { print -r -- "$(ag_state_dir)/pids"; }

write_latest_telemetry() {
  local event="$1" ok="$2" detail_json="${3:-{}}" extra_json="${4:-{}}"
  local out="${OLUKA_TELEMETRY_DIR}/antigravity.latest.json"
  mkdir -p "$(ag_state_dir)" "$(ag_pid_dir)"
  print -r -- "{\"ts\":\"$(oluka_ts_utc)\",\"agent\":\"${AGENT}\",\"event\":\"${event}\",\"ok\":${ok},\"detail\":${detail_json},\"extra\":${extra_json}}" > "${out}"
}

usage() {
  cat <<'USAGE'
antigravity.zsh (0luka)
Commands:
  antigravity.zsh exec -- <cmd...>
  antigravity.zsh warp <dir> -- <cmd...>
  antigravity.zsh cleanup [--scope temp|artifacts|logs] [--risky --yes]
  antigravity.zsh help
Notes:
  - Destructive operations require --risky and --yes.
USAGE
}

safe_execute() {
  # Runs command, captures failure without killing strict-mode parent.
  local cmd=("$@")
  [[ ${#cmd[@]} -gt 0 ]] || { log_err "exec requires a command"; exit 64; }

  write_latest_telemetry "exec" true "{\"cmd\":\"(redacted)\"}" "{}"
  log_info "[antigravity] exec: ${cmd[*]}"

  set +e
  "${cmd[@]}"
  local st=$?
  set -e

  write_latest_telemetry "exec_done" true "{\"exit_code\":${st}}" "{}"
  return "${st}"
}

warp() {
  local dir="${1:-}"
  shift || true
  [[ -n "${dir}" ]] || { log_err "warp requires <dir>"; exit 64; }

  if [[ "${1:-}" == "--" ]]; then shift; else log_err "warp requires -- before command"; exit 64; fi
  local cmd=("$@")
  [[ ${#cmd[@]} -gt 0 ]] || { log_err "warp requires command after --"; exit 64; }

  # subshell isolates directory change
  (
    cd "${dir}" || { log_err "cannot cd: ${dir}"; exit 1; }
    log_info "[antigravity] warp@$(pwd): ${cmd[*]}"
    "${cmd[@]}"
  )
}

cleanup_scope() {
  local scope="${1:-temp}"
  local risky=0 yes=0
  shift || true

  while (( $# )); do
    case "$1" in
      --risky) risky=1; shift ;;
      --yes) yes=1; shift ;;
      --scope) scope="${2:-temp}"; shift 2 ;;
      *) log_err "unknown arg: $1"; exit 64 ;;
    esac
  done

  # Refuse destructive cleanup unless explicitly allowed
  if (( risky == 0 || yes == 0 )); then
    write_latest_telemetry "cleanup_refused" true "{\"scope\":\"${scope}\"}" "{\"need\":\"--risky --yes\"}"
    log_warn "[antigravity] cleanup refused (need --risky --yes)"
    exit 77
  fi

  local target=""
  case "${scope}" in
    temp) target="${OLUKA_ROOT}/.tmp" ;;
    artifacts) target="${OLUKA_ROOT}/artifacts" ;;
    logs) target="${OLUKA_LOG_DIR}" ;;
    *) log_err "unknown cleanup scope: ${scope}"; exit 64 ;;
  esac

  # Safety: must be inside repo root
  local abs="${target:A}"
  local root="${OLUKA_ROOT:A}"
  [[ "${abs}" == "${root}"* ]] || { log_err "refuse cleanup outside repo root"; exit 77; }

  write_latest_telemetry "cleanup" true "{\"scope\":\"${scope}\",\"target\":\"${target}\"}" "{}"
  log_warn "[antigravity] cleanup: ${target}"
  rm -rf -- "${target}"
  write_latest_telemetry "cleanup_done" true "{\"scope\":\"${scope}\"}" "{}"
  print -r -- "[antigravity] cleanup done: ${scope}"
}

main() {
  mkdir -p "$(ag_state_dir)" "$(ag_pid_dir)"

  local cmd="${1:-help}"
  shift || true

  case "${cmd}" in
    exec)
      [[ "${1:-}" == "--" ]] || { log_err "exec requires --"; exit 64; }
      shift
      safe_execute "$@"
      ;;
    warp)
      local dir="${1:-}"; shift || true
      warp "${dir}" "$@"
      ;;
    cleanup)
      cleanup_scope "$@"
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      log_err "unknown command: ${cmd}"
      exit 64
      ;;
  esac
}

main "$@"
