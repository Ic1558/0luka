#!/usr/bin/env zsh
set -euo pipefail

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin"

ROOT="${LUKA_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
OBS="$ROOT/observability"

# --- GUARD CHECK: Validate Root ---
if [[ ! -f "$ROOT/luka.md" ]]; then
  echo "❌ FATAL: Root validation failed. $ROOT/luka.md not found."
  exit 1
fi

# Inputs (adjust if your actual folders differ)
TASKS_DIR="$ROOT/artifacts/tasks/pending"
BRIDGE_INBOX="$ROOT/artifacts/tasks/pending"
BRIDGE_INFLIGHT="$ROOT/interface/processing/tasks"
DASH_PROGRESS="$OBS/dashboard/progress"
DASH_RESULTS="$OBS/dashboard/results"
REPORTS_DIR="$OBS/reports"
RETENTION_DIR="$OBS/retention/briefings"
QUARANTINE_DIR="$OBS/quarantine"

BRIEFING_WINDOW_HRS="${BRIEFING_WINDOW_HRS:-12}"

mkdir -p "$DASH_PROGRESS" "$RETENTION_DIR"

NOW_UTC="$(/bin/date -u +"%Y-%m-%dT%H:%M:%SZ")"
STAMP="$(/bin/date -u +"%Y%m%d_%H%M")"
WINDOW_START="$(/bin/date -u -v -"${BRIEFING_WINDOW_HRS}"H +"%Y-%m-%dT%H:%M:%SZ")"
WINDOW_END="$NOW_UTC"
LATEST_MD="$DASH_PROGRESS/latest.md"
LATEST_JSON="$DASH_PROGRESS/latest.json"

# --- GUARD CHECK: Fail hard if target is not the canonical progress dashboard ---
if [[ "${LATEST_MD:t}" != "latest.md" ]] || [[ "${LATEST_MD:h:t}" != "progress" ]]; then
  echo "❌ FATAL: Safety lock. $0 must write to .../progress/latest.md"
  exit 1
fi

ARCHIVE_MD="$RETENTION_DIR/briefing_${STAMP}.md"
ARCHIVE_JSON="$RETENTION_DIR/briefing_${STAMP}.json"

# --- POINT 3: Advisory Locking (Advisory Lock) ---
LOCKDIR="$DASH_PROGRESS/.build_lock"
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  echo "❌ FATAL: Another build is running: $LOCKDIR"
  exit 1
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null || true' EXIT

# Helper: count files safely (0 if missing)
count_files() {
  local d="$1"
  [[ -d "$d" ]] || { echo 0; return; }
  /usr/bin/find "$d" -type f 2>/dev/null | /usr/bin/wc -l | /usr/bin/tr -d ' '
}

# Count task-ish things
TASK_JSON="$(count_files "$TASKS_DIR")"
INBOX_N="$(count_files "$BRIDGE_INBOX")"
INFLIGHT_N="$(count_files "$BRIDGE_INFLIGHT")"
RESULTS_N="$(count_files "$DASH_RESULTS")"
REPORTS_N="$(count_files "$REPORTS_DIR")"
RETENTION_N="$(count_files "$RETENTION_DIR")"
QUAR_N="$(count_files "$QUARANTINE_DIR")"

# Grab a few latest filenames for fast scan (not parsing content)
latest_list() {
  local d="$1" n="${2:-8}"
  [[ -d "$d" ]] || return 0
  /bin/ls -1t "$d" 2>/dev/null | /usr/bin/head -n "$n" | /usr/bin/sed 's/^/- /'
}

# Build markdown (simple + deterministic)
render_md() {
  cat <<MD
<!-- built_by=tools/briefing/build_briefing.zsh timestamp=${NOW_UTC} -->
# 0luka Situation Briefing
- Generated: ${NOW_UTC}
- Root: ${ROOT}
- Window: ${WINDOW_START} → ${WINDOW_END}

Counts
- tasks: ${TASK_JSON}
- inbox: ${INBOX_N}
- inflight: ${INFLIGHT_N}
- results: ${RESULTS_N}
- reports: ${REPORTS_N}
- retention: ${RETENTION_N}
- quarantine: ${QUAR_N}

Latest items (filenames only)
Inbox:
$(latest_list "$BRIDGE_INBOX" 10)
Inflight:
$(latest_list "$BRIDGE_INFLIGHT" 10)
Results:
$(latest_list "$DASH_RESULTS" 10)
Reports:
$(latest_list "$REPORTS_DIR" 10)
Quarantine:
$(latest_list "$QUARANTINE_DIR" 10)

Pointers
- tasks: ${TASKS_DIR}
- inbox: ${BRIDGE_INBOX}
- inflight: ${BRIDGE_INFLIGHT}
- results: ${DASH_RESULTS}
- reports: ${REPORTS_DIR}
- progress: ${DASH_PROGRESS}
- retention: ${RETENTION_DIR}
- quarantine: ${QUARANTINE_DIR}
MD
}

TMP="$(mktemp)"
render_md > "$TMP"

# --- POINT 1: Atomic Move ---
/bin/cp "$TMP" "${ARCHIVE_MD}.tmp"
/bin/mv -f "${ARCHIVE_MD}.tmp" "$ARCHIVE_MD"
/bin/mv -f "$TMP" "$LATEST_MD"

# --- POINT 2 & 3: Self-Check after mv ---
if [[ ! -s "$LATEST_MD" ]] || ! /usr/bin/grep -q "Window:" "$LATEST_MD"; then
  echo "❌ FATAL: Self-check failed for $LATEST_MD (empty or corrupt)" >&2
  exit 1
fi

# JSON sidecar (briefing.v1)
PYTHON_BIN="/opt/homebrew/bin/python3"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="/usr/bin/python3"
fi

export ROOT
export NOW_UTC
export WINDOW_START
export WINDOW_END
export LATEST_JSON
export ARCHIVE_JSON

"$PYTHON_BIN" - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ["ROOT"]).resolve()
window_start = os.environ.get("WINDOW_START", "")
window_end = os.environ.get("WINDOW_END", "")
generated_at = os.environ.get("NOW_UTC", "")

def list_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    files = []
    for p in path.rglob("*"):
        if p.is_file():
            files.append(p)
    return files

def extract_task_id(path: Path) -> str:
    def normalize(value: str) -> str:
        if not value:
            return ""
        if len(value) > 120:
            return ""
        if any(ch.isspace() for ch in value):
            return ""
        if any(ch in value for ch in "{}[]"):
            return ""
        return value

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return path.name
    # JSON key
    for key in ("task_id", "id"):
        idx = text.find(f'"{key}"')
        if idx != -1:
            snippet = text[idx:idx+200]
            for part in snippet.split("\n"):
                if '"' + key + '"' in part:
                    try:
                        value = part.split(":", 1)[1].strip().strip(",")
                        value = value.strip('"')
                        value = normalize(value)
                        if value:
                            return value
                    except Exception:
                        pass
    # YAML-like
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("task_id") and ":" in line:
            try:
                value = line.split(":", 1)[1].strip().strip('"')
            except Exception:
                value = ""
            value = normalize(value)
            if value:
                return value
    return path.name

def ids_from_dir(path: Path) -> list[str]:
    if not path.exists():
        return []
    ids = set()
    # If path is pending/open tasks dir, it might have subdirs named by task_id
    for item in path.iterdir():
        if item.is_dir():
            ids.add(item.name)
        elif item.is_file():
            ids.add(extract_task_id(item))
    return sorted(ids)

obs = root / "observability"
inbox_dir = root / "artifacts" / "tasks" / "pending"
inflight_dir = root / "interface" / "processing" / "tasks"
results_dir = obs / "dashboard" / "results"
reports_dir = obs / "reports"
quarantine_dir = obs / "quarantine"
tasks_dir = root / "artifacts" / "tasks" / "pending"
retention_dir = obs / "retention" / "briefings"
followup_dir = obs / "retention" / "tasks"

inbox_ids = ids_from_dir(inbox_dir)
inflight_ids = ids_from_dir(inflight_dir)
result_ids = ids_from_dir(results_dir)
report_ids = ids_from_dir(reports_dir)
quarantine_ids = ids_from_dir(quarantine_dir)
task_ids = ids_from_dir(tasks_dir)
followup_ids = ids_from_dir(followup_dir)
retention_ids = [p.name for p in list_files(retention_dir) if p.name.startswith("briefing_")]

def failed_ids_from_reports() -> list[str]:
    failed = set()
    for p in list_files(reports_dir):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if '"status"' in text or 'status:' in text:
            if "failed" in text.lower():
                failed.add(extract_task_id(p))
    return sorted(failed)

failed_ids = failed_ids_from_reports()

latest_json_path = Path(os.environ.get("LATEST_JSON", ""))
prev = None
baseline = "first_run"
baseline_reason = None
baseline_prev_generated_at = None

if latest_json_path.exists():
    try:
        prev = json.loads(latest_json_path.read_text(encoding="utf-8"))
        baseline = "rolling"
        baseline_prev_generated_at = prev.get("generated_at")
    except Exception as e:
        baseline = "prev_unreadable"
        baseline_reason = str(e)[:100]
        prev = None

def prev_set(key: str) -> set[str]:
    if not prev:
        return set()
    return set(prev.get("sets", {}).get(key, []) or [])

prev_inbox = prev_set("inbox")
prev_inflight = prev_set("inflight")
prev_quarantine = prev_set("quarantined")

cur_inbox = set(inbox_ids)
cur_inflight = set(inflight_ids)
cur_quarantine = set(quarantine_ids)

# Compute diffs only if we have a valid previous baseline
if baseline == "rolling":
    new_tasks = sorted((cur_inbox | cur_inflight) - (prev_inbox | prev_inflight))
    resolved = sorted((prev_inbox | prev_inflight) - (cur_inbox | cur_inflight))
    quarantined = sorted(cur_quarantine - prev_quarantine)
    stuck = sorted(cur_inflight & prev_inflight)
else:
    # No valid baseline: zero out all diffs
    new_tasks = []
    resolved = []
    quarantined = []
    stuck = []

diff = {
    "new_tasks": new_tasks,
    "resolved": resolved,
    "stuck": stuck,
    "quarantined": quarantined,
}
diff_counts = {k: len(v) for k, v in diff.items()}


pointers = {
    "pending": "artifacts/tasks/pending",
    "inflight": "interface/processing/tasks",
    "results": "observability/dashboard/results",
    "reports": "observability/reports",
    "progress": "observability/dashboard/progress",
    "retention": "observability/retention/briefings",
    "quarantine": "observability/quarantine",
    "tasks": "artifacts/tasks/pending",
}

actionable = {
    "needs_approval": [{"task_id": t, "path": pointers["quarantine"], "hint": "search by task_id"} for t in quarantined],
    "retry_suggested": [{"task_id": t, "path": pointers["reports"], "hint": "search by task_id"} for t in failed_ids],
    "missing_input": [],
}

for p in list_files(reports_dir):
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    if "missing input" in text.lower() or "need input" in text.lower():
        actionable["missing_input"].append({"task_id": extract_task_id(p), "path": pointers["reports"], "hint": "search by task_id"})

doc = {
    "schema_version": "briefing.v1",
    "generated_at": generated_at,
    "baseline": baseline,
    "baseline_prev_generated_at": baseline_prev_generated_at,
    "baseline_reason": baseline_reason,
    "window": {"start": window_start, "end": window_end},
    "root": str(root),
    "counts": {
        "tasks": len(task_ids),
        "inbox": len(inbox_ids),
        "inflight": len(inflight_ids),
        "done": len(result_ids),
        "failed": len(failed_ids),
        "quarantined": len(quarantine_ids),
        "followups": len(followup_ids),
        "retention": len(retention_ids),
    },
    "diff": diff,
    "diff_counts": diff_counts,
    "actionable": actionable,
    "pointers": pointers,
    "themes": [],

    "sets": {
        "inbox": inbox_ids,
        "inflight": inflight_ids,
        "results": result_ids,
        "reports": report_ids,
        "quarantined": quarantine_ids,
    },
}

latest_json_path.parent.mkdir(parents=True, exist_ok=True)
archive_json_path = Path(os.environ.get("ARCHIVE_JSON", ""))
if not latest_json_path.name or not archive_json_path.name:
    raise SystemExit("missing LATEST_JSON or ARCHIVE_JSON")
archive_json_path.parent.mkdir(parents=True, exist_ok=True)

latest_json_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
archive_json_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

# --- POINT 4: Health Marker (Success) ---
HEALTH_MARKER="$DASH_PROGRESS/briefing_last_ok.json"
"${PYTHON_BIN}" -c 'import json,sys,time; print(json.dumps({"ts":sys.argv[1],"window_end":sys.argv[2],"status":"ok"}))' "${NOW_UTC}" "${WINDOW_END}" > "${HEALTH_MARKER}"

echo "OK: wrote"
echo " - $LATEST_MD ($(wc -c < "$LATEST_MD" | xargs) bytes)"
echo " - $LATEST_JSON"
echo " - $HEALTH_MARKER"
echo " - $ARCHIVE_MD"
