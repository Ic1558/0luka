#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-${LUKA_SOT:-${HOME}/0luka}}"
SAVE_CMD="${SAVE_NOW_CMD:-save-now}"
RUN_TOOL="/Users/icmini/02luka/tools/run_tool.zsh"

agent_id=""
trace_id=""
phase=""
task_id=""
topic=""
files=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent-id)
      agent_id="$2"
      shift 2
      ;;
    --trace-id)
      trace_id="$2"
      shift 2
      ;;
    --phase)
      phase="$2"
      shift 2
      ;;
    --task-id)
      task_id="$2"
      shift 2
      ;;
    --topic)
      topic="$2"
      shift 2
      ;;
    --files)
      files="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

if [[ -z "$agent_id" || -z "$trace_id" || -z "$phase" ]]; then
  echo "missing required args" >&2
  exit 2
fi

if [[ -z "$topic" ]]; then
  topic="trace_id=${trace_id} phase=${phase} task_id=${task_id} files=${files}"
fi

export SAVE_AGENT="$agent_id"
export SAVE_SOURCE="bridge-dispatcher"
export PROJECT_ID="0luka"
export SAVE_SCHEMA_VERSION="1"
export SAVE_TRACE_ID="$trace_id"
export SAVE_PHASE="$phase"
export SAVE_TASK_ID="$task_id"

if command -v "$SAVE_CMD" >/dev/null 2>&1; then
  "$SAVE_CMD" "$topic"
  exit $?
fi

if [[ -x "$RUN_TOOL" ]]; then
  zsh "$RUN_TOOL" save "$topic"
  exit $?
fi

echo "save-now not available" >&2
exit 1
