#!/usr/bin/env zsh
set -euo pipefail
umask 077

ROOT="${ROOT:-${LUKA_SOT:-${HOME}/0luka}}"

phase=""
agent_id=""
trace_id=""
task_id=""
title=""
topic=""
in_path=""
format=""
tags=""
outdir=""

usage() {
  cat <<'USAGE' >&2
Usage: save_now.zsh --phase plan|done|reply --agent-id <id> --trace-id <id> --in <path|-> [--title <title>] [--task-id <id>] [--format md|json|txt] [--tags a,b,c] [--outdir <dir>]
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --phase)
      phase="$2"; shift 2 ;;
    --agent-id)
      agent_id="$2"; shift 2 ;;
    --trace-id)
      trace_id="$2"; shift 2 ;;
    --task-id)
      task_id="$2"; shift 2 ;;
    --title)
      title="$2"; shift 2 ;;
    --topic)
      topic="$2"; shift 2 ;;
    --in)
      in_path="$2"; shift 2 ;;
    --format)
      format="$2"; shift 2 ;;
    --tags)
      tags="$2"; shift 2 ;;
    --outdir)
      outdir="$2"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "unknown arg: $1" >&2
      usage; exit 2 ;;
  esac
done

if [[ -z "${title}" && -n "${topic}" ]]; then
  title="${topic}"
fi

if [[ -z "${phase}" || -z "${agent_id}" || -z "${trace_id}" || -z "${in_path}" ]]; then
  echo "missing required args" >&2
  usage
  exit 2
fi

if [[ ! "${phase}" =~ ^(plan|done|reply)$ ]]; then
  echo "invalid phase: ${phase}" >&2
  exit 2
fi

if [[ ! "${agent_id}" =~ ^[a-z0-9._-]+$ ]]; then
  echo "invalid agent_id: ${agent_id}" >&2
  exit 2
fi

if [[ "${trace_id}" == *"/"* || "${trace_id}" == *".."* ]]; then
  echo "invalid trace_id: ${trace_id}" >&2
  exit 2
fi

if [[ -z "${title}" ]]; then
  title="trace_id=${trace_id} phase=${phase}"
fi

task_dir="${outdir:-${ROOT}/observability/artifacts/tasks/${trace_id}}"
mkdir -p "${task_dir}"

tmp_in=""
cleanup() {
  if [[ -n "${tmp_in}" && -f "${tmp_in}" ]]; then
    rm -f "${tmp_in}" || true
  fi
}
trap cleanup EXIT

input_file="${in_path}"
if [[ "${in_path}" == "-" ]]; then
  tmp_in="$(mktemp "${task_dir}/.stdin.XXXXXX")"
  cat > "${tmp_in}"
  input_file="${tmp_in}"
elif [[ ! -f "${in_path}" ]]; then
  echo "input file missing: ${in_path}" >&2
  exit 2
fi

if [[ -z "${format}" ]]; then
  case "${input_file##*.}" in
    json) format="json" ;;
    md) format="md" ;;
    txt) format="txt" ;;
    *) format="md" ;;
  esac
fi

target_name=""
case "${phase}" in
  plan)
    target_name="plan.md"
    ;;
  done)
    if [[ "${format}" == "json" ]]; then
      target_name="done.json"
    else
      target_name="done.md"
    fi
    ;;
  reply)
    target_name="reply.md"
    ;;
esac

target_path="${task_dir}/${target_name}"
tmp_out="$(mktemp "${task_dir}/.${target_name}.XXXXXX")"
cat "${input_file}" > "${tmp_out}"
mv -f "${tmp_out}" "${target_path}"

if [[ "${phase}" == "done" && "${format}" == "json" ]]; then
  if ! python3 - "${target_path}" >/dev/null 2>&1 <<'PY'
import json, sys
json.load(open(sys.argv[1], "r", encoding="utf-8"))
PY
  then
    echo "invalid json content for done phase" >&2
    exit 4
  fi
fi

meta_path="${task_dir}/meta.json"
timeline_path="${task_dir}/timeline.jsonl"
handoff_path="${ROOT}/observability/artifacts/handoff_latest.json"

python3 - <<'PY' \
  "${meta_path}" \
  "${trace_id}" \
  "${task_id}" \
  "${agent_id}" \
  "${title}" \
  "${phase}" \
  "${target_name}" \
  "${tags}" \
  "${timeline_path}" \
  "${handoff_path}" \
  "${task_dir}"
import json, sys, time
from pathlib import Path

meta_path = Path(sys.argv[1])
trace_id = sys.argv[2]
task_id = sys.argv[3]
agent_id = sys.argv[4]
title = sys.argv[5]
phase = sys.argv[6]
rel_path = sys.argv[7]
tags = sys.argv[8]
timeline_path = Path(sys.argv[9])
handoff_path = Path(sys.argv[10])
task_dir = Path(sys.argv[11])

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def read_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

meta = read_json(meta_path)
meta.setdefault("trace_id", trace_id)
if task_id:
    meta["task_id"] = task_id
meta["title"] = title
meta["agent_id"] = agent_id
meta.setdefault("created_at", now())
meta["updated_at"] = now()
meta.setdefault("phases", {})
meta["phases"][phase] = {"path": rel_path, "ts": now()}

status = meta.get("status", "IN_PROGRESS")
if phase == "done":
    status = "DONE"
elif phase == "reply":
    status = "REPLIED"
meta["status"] = status

if tags:
    meta["tags"] = [t for t in tags.split(",") if t]

write_json(meta_path, meta)

timeline_path.parent.mkdir(parents=True, exist_ok=True)
entry = {
    "ts": now(),
    "trace_id": trace_id,
    "task_id": task_id,
    "agent_id": agent_id,
    "phase": phase,
    "path": rel_path,
    "title": title,
}
with timeline_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

handoff = {
    "ts": now(),
    "trace_id": trace_id,
    "title": title,
    "agent_id": agent_id,
    "updated_at": meta["updated_at"],
    "dir": str(task_dir),
    "paths": {
        "meta": str(meta_path),
        "plan": str(task_dir / "plan.md"),
        "done": str(task_dir / "done.json"),
        "reply": str(task_dir / "reply.md"),
    },
}
write_json(handoff_path, handoff)
PY

exit 0
