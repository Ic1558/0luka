#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-${LUKA_SOT:-${HOME}/0luka}}"
SAVE_NOW="${ROOT}/tools/save_now.zsh"

agent_id=""
trace_id=""
phase=""
task_id=""
topic=""
files=""
input_file=""

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

if [[ -n "$files" ]]; then
  IFS=',' read -rA file_list <<< "$files"
  for f in "${file_list[@]}"; do
    case "$phase" in
      plan)
        if [[ "$f" == *"plan.md" ]]; then input_file="$f"; break; fi
        if [[ "$f" == *"plan.json" ]]; then input_file="$f"; break; fi
        ;;
      done)
        if [[ "$f" == *"result.json" ]]; then input_file="$f"; break; fi
        if [[ "$f" == *".result.json" ]]; then input_file="$f"; break; fi
        if [[ "$f" == *"done.json" ]]; then input_file="$f"; break; fi
        ;;
      reply)
        if [[ "$f" == *"reply.md" ]]; then input_file="$f"; break; fi
        ;;
    esac
  done
  if [[ -z "$input_file" ]]; then
    input_file="${file_list[1]}"
  fi
fi

if [[ -z "$input_file" || ! -f "$input_file" ]]; then
  echo "save-now wrapper: missing input file for phase=${phase}" >&2
  exit 2
fi

if [[ ! -x "$SAVE_NOW" ]]; then
  echo "save-now wrapper: missing ${SAVE_NOW}" >&2
  exit 1
fi

save_outdir="${ROOT}/observability/artifacts/tasks/${trace_id}"
save_format=""
case "${input_file##*.}" in
  json) save_format="json" ;;
  md) save_format="md" ;;
  txt) save_format="txt" ;;
esac

zsh "$SAVE_NOW" \
  --phase "$phase" \
  --agent-id "$agent_id" \
  --trace-id "$trace_id" \
  --task-id "$task_id" \
  --title "$topic" \
  --in "$input_file" \
  --outdir "$save_outdir" \
  --format "$save_format"
