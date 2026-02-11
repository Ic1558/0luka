#!/bin/zsh
set -euo pipefail

ROOT_DEFAULT="$(cd "$(dirname "$0")/../.." && pwd)"
ROOT="${COLE_RUN_ROOT:-$ROOT_DEFAULT}"
RUNS_DIR="$ROOT/cole/runs"
OBS_DIR="$ROOT/observability"

redact_text() {
  sed -E \
    -e 's#file:///Users/[^"[:space:]]+#<redacted:path>#g' \
    -e 's#/Users/[^"[:space:]]+#<redacted:path>#g' \
    -e 's#(ghp_[A-Za-z0-9_]+)#<redacted:token>#g' \
    -e 's#(sk-[A-Za-z0-9_-]+)#<redacted:token>#g' \
    -e 's#([Aa]uthorization:[[:space:]]*[Bb]earer[[:space:]]+)[^"[:space:]]+#\1<redacted:token>#g' \
    -e 's#([Bb]earer[[:space:]]+)[^"[:space:]]+#\1<redacted:token>#g' \
    -e 's#([Aa][Pp][Ii]_[Kk][Ee][Yy][=:][[:space:]]*)[^"[:space:]]+#\1<redacted:token>#g'
}

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
}

is_safe_run_id() {
  local run_id="$1"
  [[ "$run_id" =~ ^[A-Za-z0-9._-]+$ ]]
}

collect_runs() {
  if [[ ! -d "$RUNS_DIR" ]]; then
    return 0
  fi
  find "$RUNS_DIR" -mindepth 1 -maxdepth 1 \( -type d -o -type f \) -print \
    | sed -E 's#^.*/##' \
    | sed -E 's#\.json$##' \
    | LC_ALL=C sort -u
}

print_list_json() {
  local runs
  runs=$(collect_runs || true)
  local json_runs
  json_runs=$(printf "%s\n" "$runs" | python3 -c 'import json,sys; rows=[r for r in sys.stdin.read().splitlines() if r]; print(json.dumps(rows))')
  printf '{"ok":true,"command":"list","rule":"sorted_lexicographic","runs":%s}\n' "$json_runs"
}

print_latest_json() {
  local runs latest
  runs=$(collect_runs || true)
  latest=$(printf "%s\n" "$runs" | tail -n 1)
  if [[ -z "$latest" ]]; then
    echo '{"ok":false,"command":"latest","rule":"max(sorted_lexicographic)","error":"no_runs"}'
    return 1
  fi
  local latest_escaped
  latest_escaped=$(printf "%s" "$latest" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')
  printf '{"ok":true,"command":"latest","rule":"max(sorted_lexicographic)","run_id":%s}\n' "$latest_escaped"
}

print_show_json() {
  local run_id="$1"
  if ! is_safe_run_id "$run_id"; then
    echo '{"ok":false,"command":"show","error":"invalid_run_id"}'
    return 2
  fi

  local candidates=(
    "$RUNS_DIR/$run_id"
    "$RUNS_DIR/$run_id.json"
    "$RUNS_DIR/$run_id/report.md"
    "$OBS_DIR/proofs/$run_id/report.md"
    "$OBS_DIR/proofs/$run_id/result.json"
  )

  local picked=""
  for c in "${candidates[@]}"; do
    if [[ -f "$c" ]]; then
      picked="$c"
      break
    fi
  done

  if [[ -z "$picked" ]]; then
    echo '{"ok":false,"command":"show","error":"run_not_found"}'
    return 3
  fi

  local rel_path
  rel_path="${picked#$ROOT/}"
  local safe_content
  safe_content=$(cat "$picked" | redact_text)

  local path_json content_json run_id_json
  path_json=$(printf "%s" "$rel_path" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')
  content_json=$(printf "%s" "$safe_content" | json_escape)
  run_id_json=$(printf "%s" "$run_id" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')

  printf '{"ok":true,"command":"show","run_id":%s,"path":%s,"content":%s}\n' "$run_id_json" "$path_json" "$content_json"
}

cmd="${1:-}"
case "$cmd" in
  list)
    print_list_json
    ;;
  latest)
    print_latest_json
    ;;
  show)
    run_id="${2:-}"
    if [[ -z "$run_id" ]]; then
      echo '{"ok":false,"command":"show","error":"missing_run_id"}'
      exit 2
    fi
    print_show_json "$run_id"
    ;;
  *)
    echo '{"ok":false,"error":"usage: cole_run.zsh {list|latest|show <run_id>}"}'
    exit 2
    ;;
esac
