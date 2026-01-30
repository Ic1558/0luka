#!/usr/bin/env zsh
set -euo pipefail

umask 077

ROOT="${LUKA_BASE:-$HOME/0luka}"
BASE_DIR="$ROOT/observability/whiteboard"
ACTION_DIR="$BASE_DIR/actions"
SNAPSHOT_DIR="$BASE_DIR/snapshots"
POINTER_DIR="$BASE_DIR/pointers"
LOCK_DIR="$BASE_DIR/lock"
EXT=".txt"

TTL_SECONDS=300
LOCK_STALE_SECONDS=120
MAX_ACTION_BYTES=1048576
MAX_SNAPSHOT_BYTES=5242880

usage() {
  print -r -- "usage: whiteboard_print.zsh <agent|last|snapshot> [--title TITLE] [--file PATH] [--snapshot|--no-snapshot]"
}

timestamp_now() {
  python3 -c "from datetime import datetime; print(datetime.now().astimezone().isoformat(timespec='seconds'))"
}

sha256_file() {
  python3 -c "import hashlib,sys; data=open(sys.argv[1],'rb').read(); print('sha256:' + hashlib.sha256(data).hexdigest())" "$1"
}

file_bytes() {
  python3 -c "import os,sys; print(os.path.getsize(sys.argv[1]))" "$1"
}

epoch_from_ts() {
  python3 -c "from datetime import datetime; import sys; print(int(datetime.fromisoformat(sys.argv[1]).timestamp()))" "$1"
}

ensure_dirs() {
  mkdir -p "$ACTION_DIR" "$SNAPSHOT_DIR" "$POINTER_DIR" "$LOCK_DIR"
}

write_atomic() {
  local target="$1"
  local content="$2"
  local dir
  dir="${target:h}"
  local tmp
  tmp="$(mktemp "$dir/.tmp.XXXXXX")"
  print -r -- "$content" > "$tmp"
  mv -f "$tmp" "$target"
}

read_pointer_ts() {
  local line="$1"
  local ts_part="${line%% file=*}"
  print -r -- "${ts_part#ts=}"
}

mark_pointer_stale() {
  local path="$1"
  local line="$2"
  local stale_line
  if [[ "$line" == *" stale="* ]]; then
    stale_line="${line%% stale=*} stale=true"
  else
    stale_line="$line stale=true"
  fi
  write_atomic "$path" "$stale_line"
}

check_fresh() {
  local pointer_path="$1"
  if [[ ! -f "$pointer_path" ]]; then
    return 1
  fi
  local line
  line="$(<"$pointer_path")"
  local ts
  ts="$(read_pointer_ts "$line")"
  if [[ -z "$ts" ]]; then
    return 1
  fi
  local now
  now="$(date +%s)"
  local ts_epoch
  ts_epoch="$(epoch_from_ts "$ts")"
  if (( now - ts_epoch > TTL_SECONDS )); then
    mark_pointer_stale "$pointer_path" "$line"
    return 2
  fi
  return 0
}

acquire_lock() {
  local agent="$1"
  local lock_path="$LOCK_DIR/${agent}.lockdir"
  if [[ -d "$lock_path" ]]; then
    local mtime
    mtime="$(stat -f %m "$lock_path")"
    local now
    now="$(date +%s)"
    local age
    age=$(( now - mtime ))
    if (( age > LOCK_STALE_SECONDS )); then
      rm -f "$lock_path/metadata.txt" 2>/dev/null || true
      rmdir "$lock_path" 2>/dev/null || true
    else
      print -r -- "LOCKED: $lock_path" >&2
      exit 73
    fi
  fi

  mkdir "$lock_path"
  local meta="$lock_path/metadata.txt"
  local ts
  ts="$(timestamp_now)"
  print -r -- "owner_pid=$$" > "$meta"
  print -r -- "host=$(hostname)" >> "$meta"
  print -r -- "start_ts=$ts" >> "$meta"
  print -r -- "$lock_path"
}

release_lock() {
  local lock_path="$1"
  rm -f "$lock_path/metadata.txt" 2>/dev/null || true
  rmdir "$lock_path" 2>/dev/null || true
}

find_latest_snapshot() {
  python3 -c "import pathlib,sys; d=pathlib.Path(sys.argv[1]); files=[p for p in d.iterdir() if p.is_file()]; files.sort(key=lambda p: p.stat().st_mtime, reverse=True); print(str(files[0]) if files else '')" "$1"
}

copy_snapshot() {
  local src="$1"
  local dest="$2"
  local max_bytes="$3"
  python3 -c "import sys; from pathlib import Path; src=Path(sys.argv[1]); dest=Path(sys.argv[2]); max_bytes=int(sys.argv[3]); data=src.read_bytes(); truncated=len(data) > max_bytes; data=data[:max_bytes] if truncated else data; dest.write_bytes(data); print('true' if truncated else 'false')" "$src" "$dest" "$max_bytes"
}

snapshot_script_path() {
  local home_script="$HOME/.0luka/scripts/atg_multi_snap.zsh"
  local repo_script="$ROOT/interface/frontends/raycast/atg_multi_snap.zsh"
  if [[ -x "$home_script" ]]; then
    print -r -- "$home_script"
    return 0
  fi
  if [[ -x "$repo_script" ]]; then
    print -r -- "$repo_script"
    return 0
  fi
  return 1
}

run_snapshot() {
  local ts
  ts="$(timestamp_now)"
  local snap_status="missing"
  local snap_detail="snapshot_script_missing"
  local snap_path=""
  local snap_truncated="false"
  local snap_sha=""
  local snap_bytes="0"

  local script
  if script="$(snapshot_script_path)"; then
    if zsh "$script" >/dev/null 2>&1; then
      local source_dir="$ROOT/observability/artifacts/snapshots"
      local latest
      latest="$(find_latest_snapshot "$source_dir")"
      if [[ -n "$latest" ]]; then
        local dest="$SNAPSHOT_DIR/$(basename "$latest")"
        local tmp
        tmp="$(mktemp "$SNAPSHOT_DIR/.tmp.XXXXXX")"
        snap_truncated="$(copy_snapshot "$latest" "$tmp" "$MAX_SNAPSHOT_BYTES")"
        mv -f "$tmp" "$dest"
        snap_path="$dest"
        snap_sha="$(sha256_file "$dest")"
        snap_bytes="$(file_bytes "$dest")"
        snap_status="ok"
        snap_detail="snapshot_copied"
      else
        snap_status="failed"
        snap_detail="snapshot_not_found"
      fi
    else
      snap_status="failed"
      snap_detail="snapshot_run_failed"
    fi
  fi

  if [[ "$snap_status" == "ok" ]]; then
    write_atomic "$POINTER_DIR/last_snapshot$EXT" "ts=$ts file=$snap_path sha256=$snap_sha bytes=$snap_bytes truncated=$snap_truncated"
  fi

  write_atomic "$POINTER_DIR/snapshot_status$EXT" "ts=$ts status=$snap_status detail=$snap_detail"

  SNAP_STATUS="$snap_status"
  SNAP_DETAIL="$snap_detail"
  SNAP_PATH="$snap_path"
  SNAP_TRUNCATED="$snap_truncated"
  SNAP_SHA="$snap_sha"
  SNAP_BYTES="$snap_bytes"
}

print_last() {
  local pointer="$POINTER_DIR/last_action$EXT"
  if [[ ! -f "$pointer" ]]; then
    print -r -- "NO_POINTER: $pointer" >&2
    exit 66
  fi
  check_fresh "$pointer" || true
  local line
  line="$(<"$pointer")"
  local file_part="${line#* file=}"
  local file="${file_part%% *}"
  if [[ -z "$file" || ! -f "$file" ]]; then
    write_atomic "$pointer" "$line missing_target=true"
    print -r -- "$line missing_target=true" >&2
    exit 66
  fi
  print -r -- "$line"
  print -r -- "----"
  print -r -- "$(<"$file")"
}

print_snapshot_only() {
  ensure_dirs
  run_snapshot
  if [[ "$SNAP_STATUS" != "ok" ]]; then
    print -r -- "snapshot_status=$SNAP_STATUS detail=$SNAP_DETAIL" >&2
    exit 65
  fi
  print -r -- "snapshot_status=ok file=$SNAP_PATH"
}

write_action() {
  local agent_id="$1"
  local title="$2"
  local input_file="$3"
  local snapshot_enabled="$4"

  ensure_dirs

  local lock_path
  lock_path="$(acquire_lock "$agent_id")"
  trap "release_lock '$lock_path'" EXIT

  local ts
  ts="$(timestamp_now)"

  local source="stdin"
  if [[ -n "$input_file" ]]; then
    source="$input_file"
  fi

  local body
  if [[ -n "$input_file" ]]; then
    body="$(<"$input_file")"
  else
    body="$(</dev/stdin)"
  fi

  local truncated="false"
  if (( ${#body} > MAX_ACTION_BYTES )); then
    body="${body:0:$MAX_ACTION_BYTES}"
    truncated="true"
  fi

  local ts_compact
  ts_compact="$(date +%Y%m%d_%H%M%S)"
  local action_path="$ACTION_DIR/${agent_id}_${ts_compact}${EXT}"
  local current_path="$BASE_DIR/${agent_id}${EXT}"

  local tmp_action
  tmp_action="$(mktemp "$ACTION_DIR/.${agent_id}.XXXXXX")"
  {
    print -r -- "--- whiteboard"
    print -r -- "agent_id: $agent_id"
    print -r -- "ts: $ts"
    print -r -- "title: $title"
    print -r -- "source: $source"
    print -r -- "---"
    print -r -- "$body"
  } > "$tmp_action"
  mv -f "$tmp_action" "$action_path"

  local tmp_current
  tmp_current="$(mktemp "$BASE_DIR/.${agent_id}.XXXXXX")"
  cp -f "$action_path" "$tmp_current"
  mv -f "$tmp_current" "$current_path"

  local action_sha
  action_sha="$(sha256_file "$action_path")"
  local action_bytes
  action_bytes="$(file_bytes "$action_path")"

  local post_status="ok"
  local snapshot_status="missing"

  if [[ "$snapshot_enabled" == "true" ]]; then
    run_snapshot
    snapshot_status="$SNAP_STATUS"
    if [[ "$SNAP_STATUS" != "ok" ]]; then
      post_status="failed"
    fi
  else
    local status_ts
    status_ts="$(timestamp_now)"
    write_atomic "$POINTER_DIR/snapshot_status$EXT" "ts=$status_ts status=missing detail=snapshot_disabled"
  fi

  local last_action_line
  last_action_line="ts=$ts file=$action_path sha256=$action_sha bytes=$action_bytes truncated=$truncated post_status=$post_status snapshot_status=$snapshot_status"
  write_atomic "$POINTER_DIR/last_action$EXT" "$last_action_line"
}

main() {
  if [[ $# -lt 1 ]]; then
    usage
    exit 64
  fi

  local command="$1"
  shift

  if [[ "$command" == "last" ]]; then
    print_last
    return 0
  fi

  if [[ "$command" == "snapshot" ]]; then
    print_snapshot_only
    return 0
  fi

  local agent_id="$command"
  local title="whiteboard"
  local input_file=""
  local snapshot_enabled="false"

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --title)
        title="$2"
        shift 2
        ;;
      --file)
        input_file="$2"
        shift 2
        ;;
      --no-snapshot)
        snapshot_enabled="false"
        shift
        ;;
      --snapshot|--snap)
        snapshot_enabled="true"
        shift
        ;;
      --help)
        usage
        exit 0
        ;;
      *)
        print -r -- "unknown arg: $1" >&2
        usage
        exit 64
        ;;
    esac
  done

  if [[ -z "$agent_id" ]]; then
    usage
    exit 64
  fi

  write_action "$agent_id" "$title" "$input_file" "$snapshot_enabled"
}

main "$@"
