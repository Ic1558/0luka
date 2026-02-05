#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
DAILY_DIR="${DAILY_DIR:-$ROOT/observability/artifacts/daily}"
INC_DIR="${INC_DIR:-$ROOT/observability/artifacts/incidents}"
PIN_EXT="${PIN_EXT:-.pin}"

usage() {
  print "Usage:"
  print "  promote.zsh daily <snapshot_path> --title \"...\" --reason \"...\" [--task TASK-...] [--trace TRACE-...]"
  print "  promote.zsh incident <snapshot_path> --title \"...\" --reason \"...\" --slug \"short-slug\" [--task ...] [--trace ...]"
  exit 1
}

(( $# >= 2 )) || usage
TYPE="$1"; SNAP="$2"; shift 2
[[ -f "$SNAP" ]] || { print "ERROR: snapshot not found: $SNAP"; exit 1; }

TITLE=""; REASON=""; TASK_ID=""; TRACE_ID=""; SLUG=""
while (( $# )); do
  case "$1" in
    --title) TITLE="$2"; shift 2;;
    --reason) REASON="$2"; shift 2;;
    --task) TASK_ID="$2"; shift 2;;
    --trace) TRACE_ID="$2"; shift 2;;
    --slug) SLUG="$2"; shift 2;;
    *) print "Unknown arg: $1"; usage;;
  esac
done
[[ -n "$TITLE" && -n "$REASON" ]] || { print "ERROR: --title and --reason required"; exit 1; }

base="${SNAP:t}"
ymd="$(echo "$base" | sed -nE 's/^SNAP-([0-9]{8})-.*/\1/p')"
hms="$(echo "$base" | sed -nE 's/^SNAP-[0-9]{8}-([0-9]{6})-.*/\1/p')"
[[ -n "$ymd" && -n "$hms" ]] || { print "ERROR: snapshot filename must start with SNAP-YYYYMMDD-HHMMSS-"; exit 1; }

now="$(date +%Y%m%d-%H%M%S)"

# pin the source snapshot
touch "${SNAP}${PIN_EXT}"

mk_meta() {
  local out="$1"
  python3 - "$TYPE" "$TITLE" "$REASON" "$TASK_ID" "$TRACE_ID" "$SNAP" "$now" > "$out" <<'PY'
import json, sys
type_, title, reason, task_id, trace_id, snap, created = sys.argv[1:]
print(json.dumps({
  "type": type_,
  "title": title,
  "reason": reason,
  "task_id": task_id or "",
  "trace_id": trace_id or "",
  "source_snapshot": snap,
  "created_at": created
}, indent=2))
PY
}

if [[ "$TYPE" == "daily" ]]; then
  outdir="${DAILY_DIR}/${ymd}"
  mkdir -p "${outdir}/evidence"
  cp -n "$SNAP" "${outdir}/evidence/${base}"
  mk_meta "${outdir}/meta.json"
  cat > "${outdir}/daily.md" <<MD
# Daily Summary — ${ymd}

## Title
${TITLE}

## Reason
${REASON}

## Evidence
- ${base}

## IDs
- task_id: ${TASK_ID}
- trace_id: ${TRACE_ID}
MD
  print "PROMOTED (daily) -> ${outdir}"
  exit 0
fi

if [[ "$TYPE" == "incident" ]]; then
  [[ -n "$SLUG" ]] || { print "ERROR: --slug required for incident"; exit 1; }
  outdir="${INC_DIR}/INC-${ymd}-${hms}-${SLUG}"
  mkdir -p "${outdir}/evidence"
  cp -n "$SNAP" "${outdir}/evidence/${base}"
  mk_meta "${outdir}/meta.json"
  cat > "${outdir}/incident.md" <<MD
# Incident — ${TITLE}

## Summary
${REASON}

## Impact
- (fill)

## Timeline
- ${ymd} ${hms}: snapshot captured (${base})
- (fill)

## Root cause
- (fill)

## Fix / Mitigation
- (fill)

## Follow-ups
- (fill)

## Evidence
- ${base}

## IDs
- task_id: ${TASK_ID}
- trace_id: ${TRACE_ID}
MD
  print "PROMOTED (incident) -> ${outdir}"
  exit 0
fi

print "ERROR: type must be daily or incident"
exit 1
