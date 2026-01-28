#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
ROOT="${ROOT%/}"

origin=""
intent=""
payload=""
payload_file=""
reply_to=""
task_id=""
payload_json=0
schema_version=""

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

while (( $# )); do
  case "$1" in
    --origin) origin="${2:-}"; shift 2 ;;
    --intent) intent="${2:-}"; shift 2 ;;
    --payload) payload="${2:-}"; shift 2 ;;
    --payload-json) payload="${2:-}"; payload_json=1; shift 2 ;;
    --payload-file) payload_file="${2:-}"; shift 2 ;;
    --reply-to) reply_to="${2:-}"; shift 2 ;;
    --task-id) task_id="${2:-}"; shift 2 ;;
    --schema-version) schema_version="${2:-}"; shift 2 ;;
    *) print -r -- "[ERR ] unknown arg: $1" >&2; exit 64 ;;
  esac
done

[[ -n "${origin}" ]] || { print -r -- "[ERR ] --origin required" >&2; exit 64; }
[[ -n "${intent}" ]] || { print -r -- "[ERR ] --intent required" >&2; exit 64; }

if [[ -n "${payload_file}" ]]; then
  if [[ ! -f "${payload_file}" ]]; then
    print -r -- "[ERR ] payload file not found: ${payload_file}" >&2
    exit 66
  fi
  payload="$(/bin/cat "${payload_file}")"
fi

[[ -n "${payload}" ]] || { print -r -- "[ERR ] --payload or --payload-file required" >&2; exit 64; }

if [[ -z "${task_id}" ]]; then
  task_id="$(${python_bin} -c 'import uuid; print(uuid.uuid4().hex)')"
fi

if [[ -z "${reply_to}" ]]; then
  reply_to="${origin}"
fi

ts_iso="$(/bin/date -u +%Y-%m-%dT%H:%M:%SZ)"
ts_file="$(/bin/date -u +%Y%m%dT%H%M%SZ)"
inbox_dir="${ROOT}/observability/bridge/inbox/${origin}"
out_file="${inbox_dir}/${ts_file}_${task_id}.task.json"

/bin/mkdir -p "${inbox_dir}"

"${python_bin}" -c 'import json,sys
path=sys.argv[1]
payload=sys.argv[6]
json_mode=sys.argv[8]
schema_version=sys.argv[9]
if json_mode == "1":
    payload=json.loads(payload)
if isinstance(payload, dict) and schema_version:
    payload.setdefault("schema_version", schema_version)
if isinstance(payload, dict) and not schema_version:
    if sys.argv[5] in {"task.emit", "task.progress", "task.result"}:
        payload.setdefault("schema_version", "1.1")
data={
  "task_id": sys.argv[2],
  "ts": sys.argv[3],
  "origin": sys.argv[4],
  "intent": sys.argv[5],
  "payload": payload,
  "reply_to": sys.argv[7],
}
with open(path,"w",encoding="utf-8") as handle:
    handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")' "${out_file}" "${task_id}" "${ts_iso}" "${origin}" "${intent}" "${payload}" "${reply_to}" "${payload_json}" "${schema_version}"

print -r -- "OK: task emitted -> ${out_file}"
