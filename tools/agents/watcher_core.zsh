#!/bin/zsh

setopt err_return no_unset pipe_fail

usage() {
  cat <<'EOF'
Usage: watcher_core.zsh [--help]

Environment:
  AGENT_NAME
  AI_INBOX_ROOT
  WORKING_DIR
  LOG_DIR
EOF
}

write_marker() {
  local path="$1"
  local content="${2:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
  local tmp="${path}.tmp"
  printf '%s\n' "$content" > "$tmp" && /bin/mv "$tmp" "$path"
}

write_artifact() {
  local path="$1"
  local content="$2"
  local tmp="${path}.tmp"
  printf '%s\n' "$content" > "$tmp" && /bin/mv "$tmp" "$path"
}

wo_id_from_file() {
  local wo_file="$1"
  /usr/bin/basename "$wo_file" .md
}

is_terminal() {
  local wo_id="$1"
  [[ -f "${STATE_DIR}/${wo_id}.done" ]]
}

is_active() {
  local wo_id="$1"
  [[ ! -f "${STATE_DIR}/${wo_id}.done" ]] && \
    ([[ -f "${STATE_DIR}/${wo_id}.accepted" ]] || [[ -f "${STATE_DIR}/${wo_id}.planned" ]])
}

is_terminal_agent() {
  case "${AGENT_NAME}" in
    gmx|gg) return 0 ;;
    *) return 1 ;;
  esac
}

has_any_active() {
  local marker
  for marker in "${STATE_DIR}"/*.accepted(N) "${STATE_DIR}"/*.planned(N); do
    [[ -e "$marker" ]] || continue
    local wo_id="${${marker:t}%.*}"
    if is_active "$wo_id"; then
      return 0
    fi
  done
  return 1
}

scan_backlog() {
  local inbox="$1"
  /usr/bin/find "$inbox" -maxdepth 1 -type f \( -name 'WO-*.md' -o -name 'PLAN-*.md' \) -print0 | /usr/bin/xargs -0 /bin/ls -1tr 2>/dev/null
}

classify_wo() {
  local wo_file="$1"
  local wo_name="${wo_file:t}"
  if /usr/bin/grep -qi 'DEFINITION OF DONE' "$wo_file"; then
    printf '%s\n' "READY"
  elif [[ "$wo_name" == PLAN-* ]] || /usr/bin/grep -q 'PLAN-ONLY' "$wo_file"; then
    printf '%s\n' "PLAN-ONLY"
  else
    printf '%s\n' "UNCLEAR"
  fi
}

release_queue() {
  has_any_active && return 1
  local queued
  for queued in "${STATE_DIR}"/*.queued(N); do
    [[ -e "$queued" ]] || continue
    local wo_id="${${queued:t}%.*}"
    [[ -f "${INBOX_DIR}/${wo_id}.md" ]] || continue
    [[ -f "${STATE_DIR}/${wo_id}.done" ]] && continue
    printf '%s\n' "${INBOX_DIR}/${wo_id}.md"
    return 0
  done
  return 1
}

dispatch_adapter() {
  local wo_file="$1"
  local adapter="${WORKING_DIR}/tools/agents/adapters/${AGENT_NAME}_invoke.zsh"
  [[ -f "$adapter" ]] || return 127
  source "$adapter"
}

write_failed_artifact() {
  local wo_id="$1"
  local agent_upper="${AGENT_NAME:u}"
  local failure_path="${AI_INBOX_ROOT}/clc/inbox/FAILED-${agent_upper}-${wo_id}.md"
  write_artifact "$failure_path" "FAILED: ${AGENT_NAME} adapter failed for ${wo_id} at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  ADAPTER_ARTIFACT_PATH="$failure_path"
}

handle_wo() {
  local wo_file="$1"
  WO_ID="$(wo_id_from_file "$wo_file")"
  WO_FILE="$wo_file"
  export WO_ID WO_FILE STATE_DIR AI_INBOX_ROOT WORKING_DIR LOG_DIR

  local seen_marker="${STATE_DIR}/${WO_ID}.seen"
  [[ -f "$seen_marker" ]] || write_marker "$seen_marker" "seen_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

  local verdict
  verdict="$(classify_wo "$wo_file")"
  export WO_VERDICT="$verdict"

  case "$verdict" in
    READY)
      is_terminal_agent || write_marker "${STATE_DIR}/${WO_ID}.accepted" "accepted_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      ;;
    PLAN-ONLY)
      write_marker "${STATE_DIR}/${WO_ID}.planned" "planned_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      ;;
    UNCLEAR)
      ADAPTER_ARTIFACT_PATH="${AI_INBOX_ROOT}/clc/inbox/BLOCKED-${WO_ID}.md"
      write_artifact "$ADAPTER_ARTIFACT_PATH" "BLOCKED: unclear WO ${WO_ID} for ${AGENT_NAME} at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
      write_marker "${STATE_DIR}/${WO_ID}.done" "done_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      return 0
      ;;
  esac

  ADAPTER_ARTIFACT_PATH=""
  local adapter_exit=0
  dispatch_adapter "$wo_file" || adapter_exit=$?

  if [[ $adapter_exit -ne 0 ]]; then
    if [[ -z "${ADAPTER_ARTIFACT_PATH}" ]] || [[ ! -f "${ADAPTER_ARTIFACT_PATH}" ]]; then
      write_failed_artifact "$WO_ID"
    fi
  fi

  if [[ -n "${ADAPTER_ARTIFACT_PATH}" ]] && [[ -f "${ADAPTER_ARTIFACT_PATH}" ]]; then
    write_marker "${STATE_DIR}/${WO_ID}.done" "done_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  fi

  return 0
}

main() {
  if [[ "${1:-}" == "--help" ]]; then
    usage
    return 0
  fi

  if [[ -z "${AGENT_NAME:-}" ]] || [[ -z "${AI_INBOX_ROOT:-}" ]]; then
    usage
    return 0
  fi

  WORKING_DIR="${WORKING_DIR:-$(pwd)}"
  LOG_DIR="${LOG_DIR:-${WORKING_DIR}/observability/logs}"
  INBOX_DIR="${AI_INBOX_ROOT}/${AGENT_NAME}/inbox"
  STATE_DIR="${AI_INBOX_ROOT}/${AGENT_NAME}/state"

  /bin/mkdir -p "$STATE_DIR" "$LOG_DIR"

  local backlog queued_target wo_file wo_id
  backlog=("${(@f)$(scan_backlog "$INBOX_DIR")}")
  queued_target="$(release_queue || true)"

  if has_any_active; then
    for wo_file in "${backlog[@]}"; do
      [[ -n "$wo_file" ]] || continue
      wo_id="$(wo_id_from_file "$wo_file")"
      is_terminal "$wo_id" && continue
      is_active "$wo_id" && continue
      [[ -f "${STATE_DIR}/${wo_id}.seen" ]] || write_marker "${STATE_DIR}/${wo_id}.seen" "seen_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
      [[ -f "${STATE_DIR}/${wo_id}.queued" ]] || write_marker "${STATE_DIR}/${wo_id}.queued" "queued_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    done
    return 0
  fi

  if [[ -n "$queued_target" ]]; then
    wo_id="$(wo_id_from_file "$queued_target")"
    /bin/rm -f "${STATE_DIR}/${wo_id}.queued"
    handle_wo "$queued_target"
    return 0
  fi

  for wo_file in "${backlog[@]}"; do
    [[ -n "$wo_file" ]] || continue
    wo_id="$(wo_id_from_file "$wo_file")"
    is_terminal "$wo_id" && continue
    handle_wo "$wo_file"
    return 0
  done

  usage
  return 0
}

main "$@"
