#!/usr/bin/env zsh
source "${0:A:h:h}/_shared/header_contract.zsh"

AGENT="liam"
VERSION="0.1.0"

liam_state_dir() {
  print -r -- "${OLUKA_STATE_DIR}/liam"
}

liam_session_file() {
  print -r -- "$(liam_state_dir)/session.current.json"
}

liam_decision_log() {
  print -r -- "$(liam_state_dir)/decision_log.jsonl"
}

write_latest_telemetry() {
  local event="$1" ok="$2" detail_json="${3:-{}}" extra_json="${4:-{}}"
  local out="${OLUKA_TELEMETRY_DIR}/liam.latest.json"
  mkdir -p "$(liam_state_dir)"
  print -r -- "{\"ts\":\"$(oluka_ts_utc)\",\"agent\":\"${AGENT}\",\"event\":\"${event}\",\"ok\":${ok},\"detail\":${detail_json},\"extra\":${extra_json}}" > "${out}"
}

append_decision() {
  local event="$1" ok="$2" detail_json="${3:-{}}" extra_json="${4:-{}}"
  local logf="$(liam_decision_log)"
  mkdir -p "$(liam_state_dir)"
  print -r -- "{\"ts\":\"$(oluka_ts_utc)\",\"agent\":\"${AGENT}\",\"event\":\"${event}\",\"ok\":${ok},\"detail\":${detail_json},\"extra\":${extra_json}}" >> "${logf}"
}

usage() {
  cat <<'USAGE'
liam.zsh (0luka)
Commands:
  liam.zsh status
  liam.zsh session start|end
  liam.zsh dispatch <module> <command> [args...]
  liam.zsh plan <text...>        (creates a plan file)
  liam.zsh run <plan_id>         (stub runner; prints plan)
Flags:
  --json   (emit minimal JSON on stdout for key operations)
USAGE
}

json_mode=0
parse_global_flags() {
  local -a rest=()
  while (( $# )); do
    case "$1" in
      --json) json_mode=1; shift ;;
      *) rest+=("$1"); shift ;;
    esac
  done
  print -r -- "${rest[@]}"
}

emit_json() {
  (( json_mode == 1 )) || return 0
  print -r -- "$1"
}

cmd_status() {
  write_latest_telemetry "status" true "{}" "{\"version\":\"${VERSION}\"}"
  append_decision "status" true "{}" "{\"version\":\"${VERSION}\"}"
  print -r -- "[liam] ok (v${VERSION})"
  emit_json "{\"ok\":true,\"agent\":\"${AGENT}\",\"version\":\"${VERSION}\"}"
}

cmd_session() {
  local sub="${1:-}"
  mkdir -p "$(liam_state_dir)"
  local f="$(liam_session_file)"

  case "${sub}" in
    start)
      local sid="sess_$(date +%s)"
      print -r -- "{\"ts\":\"$(oluka_ts_utc)\",\"session_id\":\"${sid}\",\"agent\":\"${AGENT}\",\"version\":\"${VERSION}\"}" > "${f}"
      write_latest_telemetry "session_start" true "{\"session_id\":\"${sid}\"}" "{}"
      append_decision "session_start" true "{\"session_id\":\"${sid}\"}" "{}"
      print -r -- "[liam] session started: ${sid}"
      emit_json "{\"ok\":true,\"session_id\":\"${sid}\"}"
      ;;
    end)
      if [[ -f "${f}" ]]; then
        local sid
        sid="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["session_id"])' "${f}" 2>/dev/null || print -r -- "")"
        rm -f -- "${f}"
        write_latest_telemetry "session_end" true "{\"session_id\":\"${sid}\"}" "{}"
        append_decision "session_end" true "{\"session_id\":\"${sid}\"}" "{}"
        print -r -- "[liam] session ended"
        emit_json "{\"ok\":true,\"session_id\":\"${sid}\"}"
      else
        write_latest_telemetry "session_end" true "{\"note\":\"no active session\"}" "{}"
        append_decision "session_end" true "{\"note\":\"no active session\"}" "{}"
        print -r -- "[liam] no active session"
        emit_json "{\"ok\":true,\"note\":\"no active session\"}"
      fi
      ;;
    *)
      log_err "usage: liam.zsh session start|end"
      exit 64
      ;;
  esac
}

cmd_dispatch() {
  local module="${1:-}" command="${2:-}"
  shift 2 || true

  [[ -n "${module}" && -n "${command}" ]] || { log_err "dispatch requires <module> <command>"; exit 64; }

  local target=""
  case "${module}" in
    codex) target="${OLUKA_ROOT}/skills/codex/codex.zsh" ;;
    antigravity) target="${OLUKA_ROOT}/skills/antigravity/antigravity.zsh" ;;
    *) log_err "unknown module: ${module}"; exit 2 ;;
  esac

  [[ -x "${target}" ]] || { log_err "module not executable: ${target}"; exit 2; }

  write_latest_telemetry "dispatch" true "{\"module\":\"${module}\",\"command\":\"${command}\"}" "{}"
  append_decision "dispatch" true "{\"module\":\"${module}\",\"command\":\"${command}\"}" "{}"

  "${target}" "${command}" "$@"
}

cmd_plan() {
  local text="${*:-}"
  [[ -n "${text}" ]] || { log_err "plan requires text"; exit 64; }

  mkdir -p "$(liam_state_dir)/plans"
  local pid="plan_$(date +%s)"
  local f="$(liam_state_dir)/plans/${pid}.txt"
  print -r -- "${text}" > "${f}"

  write_latest_telemetry "plan_created" true "{\"plan_id\":\"${pid}\"}" "{}"
  append_decision "plan_created" true "{\"plan_id\":\"${pid}\"}" "{}"
  print -r -- "[liam] plan created: ${pid}"
  emit_json "{\"ok\":true,\"plan_id\":\"${pid}\",\"path\":\"${f}\"}"
}

cmd_run() {
  local pid="${1:-}"
  [[ -n "${pid}" ]] || { log_err "run requires plan_id"; exit 64; }
  local f="$(liam_state_dir)/plans/${pid}.txt"
  [[ -f "${f}" ]] || { log_err "plan not found: ${pid}"; exit 66; }

  local content
  content="$(cat "${f}")"
  write_latest_telemetry "run" true "{\"plan_id\":\"${pid}\"}" "{}"
  append_decision "run" true "{\"plan_id\":\"${pid}\"}" "{}"
  print -r -- "[liam] plan(${pid}): ${content}"
  emit_json "{\"ok\":true,\"plan_id\":\"${pid}\"}"
}

main() {
  local -a args
  args=($(parse_global_flags "$@"))
  set -- "${args[@]}"

  local cmd="${1:-help}"
  shift || true
  case "${cmd}" in
    status) cmd_status ;;
    session) cmd_session "$@" ;;
    dispatch) cmd_dispatch "$@" ;;
    plan) cmd_plan "$@" ;;
    run) cmd_run "$@" ;;
    help|-h|--help) usage ;;
    *) log_err "unknown command: ${cmd}"; exit 64 ;;
  esac
}

[[ "${ZSH_EVAL_CONTEXT:-}" == *":file"* ]] && main "$@" || main "$@"
