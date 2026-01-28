#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
ROOT="${ROOT%/}"

watch_mode="${BRIDGE_WATCH_MODE:-poll}"
poll_interval="${BRIDGE_POLL_INTERVAL:-10}"
once=0

for arg in "$@"; do
  case "$arg" in
    --once) once=1 ;;
  esac
done

python_bin="${PYTHON_BIN:-}"
if [[ -z "${python_bin}" ]]; then
  python_bin="$(command -v python3 || true)"
fi
if [[ -z "${python_bin}" ]]; then
  for candidate in /opt/homebrew/bin/python3 /usr/bin/python3; do
    if [[ -x "${candidate}" ]]; then
      python_bin="${candidate}"
      break
    fi
  done
fi
[[ -n "${python_bin}" ]] || { print -r -- "[ERR ] python3 not found" >&2; exit 127; }

telemetry_path="${ROOT}/observability/telemetry/bridge_watch.latest.json"
error_log="${ROOT}/observability/bridge/errors/bridge_watch.jsonl"
processor_path="${ROOT}/tools/bridge_task_processor.py"

effective_mode="${watch_mode}"
if [[ "${effective_mode}" == "fswatch" ]]; then
  if ! command -v fswatch >/dev/null 2>&1; then
    effective_mode="poll"
  fi
fi

write_latest() {
  local state="$1"
  local note="$2"
  local last_file="$3"
  local last_event="$4"

  "${python_bin}" -c 'import json,os,sys,time
path=sys.argv[1]
state=sys.argv[2]
note=sys.argv[3]
last_file=sys.argv[4]
watch_mode=sys.argv[5]
last_event=sys.argv[6]
data={"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "module": "bridge_watch", "status": state, "note": note, "last_file": last_file}
if watch_mode:
    data["watch_mode"]=watch_mode
if last_event:
    try:
        data["last_event"]=json.loads(last_event)
    except Exception:
        pass
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8") as handle:
    handle.write(json.dumps(data, ensure_ascii=False) + "\n")' "${telemetry_path}" "${state}" "${note}" "${last_file}" "${effective_mode}" "${last_event}"
}

append_error() {
  local stage="$1"
  local reason="$2"
  local last_file="$3"

  "${python_bin}" -c 'import json,os,sys,time
path=sys.argv[1]
stage=sys.argv[2]
reason=sys.argv[3]
last_file=sys.argv[4]
event={
  "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  "module": "bridge_watch",
  "event": "error",
  "stage": stage,
  "reason": reason,
  "inbox_path": last_file,
  "inflight_path": "",
  "task_id": "",
  "agent": "",
  "exception": "",
}
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "a", encoding="utf-8") as handle:
    handle.write(json.dumps(event, ensure_ascii=False) + "\n")' "${error_log}" "${stage}" "${reason}" "${last_file}"
}

list_tasks() {
  "${python_bin}" -c 'import glob,os,sys
root=sys.argv[1]
pattern=os.path.join(root, "observability", "bridge", "inbox", "**", "*.json")
paths=[p for p in glob.glob(pattern, recursive=True) if os.path.isfile(p)]
paths.sort(key=lambda p: os.path.getmtime(p))
print("\n".join(paths))' "${ROOT}"
}

if [[ "${effective_mode}" == "fswatch" ]]; then
  write_latest "ok" "fswatch_start" "" ""
fi

while true; do
  tasks=("${(@f)$(list_tasks)}")
  if (( ${#tasks[@]} == 0 )); then
    write_latest "idle" "no_new_files" "" ""
    if (( once )); then
      exit 0
    fi
    sleep "${poll_interval}"
    continue
  fi

  for task_path in "${tasks[@]}"; do
    ts_iso="$(/bin/date -u +%Y-%m-%dT%H:%M:%SZ)"
    last_event="$(${python_bin} -c 'import json,sys; print(json.dumps({"kind":"task","path":sys.argv[1],"ts":sys.argv[2]}))' "${task_path}" "${ts_iso}")"

    if [[ ! -f "${processor_path}" ]]; then
      write_latest "error" "task_processor_missing" "${task_path}" "${last_event}"
      append_error "processor_check" "task_processor_missing" "${task_path}"
      if (( once )); then
        exit 2
      fi
      continue
    fi

    if "${python_bin}" "${processor_path}" --path "${task_path}"; then
      write_latest "ok" "ingested" "${task_path}" "${last_event}"
    else
      write_latest "error" "task_failed" "${task_path}" "${last_event}"
      append_error "processor_run" "task_failed" "${task_path}"
    fi
  done

  if (( once )); then
    exit 0
  fi

  if [[ "${effective_mode}" == "fswatch" ]] && command -v fswatch >/dev/null 2>&1; then
    fswatch -1 "${ROOT}/observability/bridge/inbox" >/dev/null 2>&1 || true
  else
    sleep "${poll_interval}"
  fi
done
