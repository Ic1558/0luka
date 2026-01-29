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

if [[ -z "${task_id}" ]]; then
  task_id="task-$(date -u +%Y%m%d-%H%M%S)-${agent_id}"
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

if [[ -z "${title}" && -n "${topic}" ]]; then
  title="${topic}"
fi

if [[ -z "${title}" || "${title}" == *"task_id="* ]]; then
  title="trace_id=${trace_id} phase=${phase} task_id=${task_id} files=${input_file}"
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
  "${input_file}" \
  "${timeline_path}" \
  "${handoff_path}" \
  "${task_dir}"
import json, sys, time
import hashlib
from pathlib import Path

meta_path = Path(sys.argv[1])
trace_id = sys.argv[2]
task_id = sys.argv[3]
agent_id = sys.argv[4]
title = sys.argv[5]
phase = sys.argv[6]
rel_path = sys.argv[7]
tags = sys.argv[8]
input_file = sys.argv[9]
timeline_path = Path(sys.argv[10])
handoff_path = Path(sys.argv[11])
task_dir = Path(sys.argv[12])

def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

def now_compact():
    return time.strftime("%Y%m%d-%H%M%S", time.gmtime())

def read_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

meta = read_json(meta_path)
meta.setdefault("schema_version", "trace-v2-meta-1")
meta.setdefault("trace_id", trace_id)
if not task_id:
    task_id = f"task-{now_compact()}-{agent_id}"
meta["task_id"] = task_id

if (not title) or ("task_id=" in title):
    title = f"trace_id={trace_id} phase={phase} task_id={task_id} files={input_file}"
meta["title"] = title
meta["agent_id"] = agent_id
meta.setdefault("created_at", now())
meta["updated_at"] = now()
meta.setdefault("phases", {})

phase_entry = meta["phases"].get(phase, {})
phase_entry.setdefault("path", rel_path)
phase_entry.setdefault("ts_start", now())
phase_entry["ts_end"] = now()
phase_entry["status"] = "DONE" if phase in {"plan", "done"} else "REPLIED"
meta["phases"][phase] = phase_entry

status = "DONE" if phase in {"plan", "done"} else "REPLIED"
meta["status"] = status
if phase == "plan":
    meta["status_reason"] = "PLAN_COMPLETE"

if tags:
    meta["tags"] = [t for t in tags.split(",") if t]
meta.setdefault("inputs", {})
files = meta["inputs"].get("files", [])
if input_file and input_file not in files:
    files.append(input_file)
meta["inputs"]["files"] = files

artifact_path = task_dir / rel_path
artifacts = phase_entry.get("artifacts", {})
artifacts[phase] = {"path": rel_path, "sha256": sha256_file(artifact_path)}
phase_entry["artifacts"] = artifacts

timeline_path.parent.mkdir(parents=True, exist_ok=True)
entry_start = {
    "ts": now(),
    "trace_id": trace_id,
    "task_id": task_id,
    "agent_id": agent_id,
    "phase": phase,
    "event": f"{phase.upper()}_START",
    "path": rel_path,
    "title": title,
}
with timeline_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(entry_start, ensure_ascii=False) + "\n")

entry_finalize = {
    "ts": now(),
    "trace_id": trace_id,
    "task_id": task_id,
    "agent_id": agent_id,
    "phase": phase,
    "event": f"{phase.upper()}_FINALIZE",
    "status": status,
    "artifacts": {
        phase: {"path": rel_path, "sha256": artifacts[phase]["sha256"]},
    },
}
with timeline_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(entry_finalize, ensure_ascii=False) + "\n")

timeline_hash = sha256_file(timeline_path)
artifacts["timeline"] = {"path": "timeline.jsonl", "sha256": timeline_hash}
phase_entry["artifacts"] = artifacts
meta["updated_at"] = now()

write_json(meta_path, meta)

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
