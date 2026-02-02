#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
IFACE_INBOX="$ROOT/interface/inbox"
IFACE_EVENTS="$ROOT/interface/module_events"
MODULE="studio"

mkdir -p "$IFACE_INBOX" "$IFACE_EVENTS" "$ROOT/.tmp" 2>/dev/null || true

_die(){ print -u2 -- "[studio] ERROR: $*"; exit 1; }

_now_utc(){
  python3 - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).isoformat().replace("+00:00","Z"))
PY
}

_hex8(){
  python3 - <<'PY'
import secrets
print(secrets.token_hex(4))
PY
}

# Fail-closed allowlist
_allow_path(){
  local p="$1"
  [[ -n "$p" ]] || return 1
  
  # Support Opal URLs and Creation Keywords
  if [[ "$p" == https://opal.google/* || "$p" == "new" || "$p" == "create" || "$p" == "NEW" || "$p" == "CREATE" ]]; then
    return 0
  fi

  [[ "$p" != /* ]] || return 1
  [[ "$p" != *".."* ]] || return 1

  # allow roots
  [[ "$p" == projects/* || "$p" == assets/* || "$p" == renders/* || "$p" == exports/* || "$p" == sandbox/* || "$p" == modules/studio/outputs/* ]] || return 1

  # hard deny
  [[ "$p" == core/* || "$p" == system/* || "$p" == tools/* || "$p" == governance/* || "$p" == runtime/* ]] && return 1
  [[ "$p" == .env* || "$p" == *.key || "$p" == *.pem ]] && return 1
  return 0
}

_usage(){
  cat <<'TXT'
studio.zsh — STUDIO Lane connector
Commands:
  studio run <kind> <rel_path|url> "<goal>"
  studio chat <kind> <rel_path|url> "<initial_goal>"
  studio opal <url> "<task>"
  studio status <request_id>
  studio tail <request_id>
  studio promote <artifact_id> --to hybrid|system

Examples:
  studio run pdf projects/demo/plan.pdf "modern lobby perspective"
  studio opal "https://opal.google/edit/..." "Add a weather node"
  studio promote art_20260202_abcdef01 --to system
TXT
}

cmd="${1:-}"; shift || true
case "$cmd" in
  opal)
    url="${1:?Opal URL required}"
    task="${2:?Task description required}"
    shift 2 || true
    ROOT="$ROOT" "$0" run opal "$url" "$task" "$@"
    ;;
  run)
    kind="${1:-}"; shift || true
    rel="${1:-}"; shift || true
    goal="${1:-}"; shift || true
    [[ -n "$kind" && -n "$rel" && -n "$goal" ]] || _die "run needs: <kind> <relative_path> \"<goal>\""

    _allow_path "$rel" || _die "path not allowed: $rel"
    if [[ "$rel" != https://opal.google/* && "$rel" != "new" && "$rel" != "create" && "$rel" != "NEW" && "$rel" != "CREATE" ]]; then
      [[ -e "$ROOT/$rel" ]] || _die "file not found: $ROOT/$rel"
    fi

    style=""
    aspect="16:9"
    res="1536x1024"
    session_id=""
    while [[ "${1:-}" != "" ]]; do
      case "$1" in
        --style) shift; style="${1:-}"; shift || true ;;
        --aspect) shift; aspect="${1:-16:9}"; shift || true ;;
        --res) shift; res="${1:-1536x1024}"; shift || true ;;
        --session) shift; session_id="${1:-}"; shift || true ;;
        *) _die "unknown flag: $1" ;;
      esac
    done

    rid="mrq_$(_now_utc | tr -d ':-' | tr -d 'TZ' | cut -c1-14)_$(_hex8)"
    created="$(_now_utc)"
    [[ -z "$session_id" ]] && session_id="ses_$(_hex8)"

    tmp="$(mktemp "$ROOT/.tmp/studio_req.XXXXXXXX")"
    out="$IFACE_INBOX/module_request_${rid}.yaml"

    cat > "$tmp" <<YAML
schema: prompt_spec_v1
request_id: ${rid}
session_id: ${session_id}
lane: studio
module: ${MODULE}
author: gmx
call_sign: "[GMX]"
created_at_utc: "${created}"

kind: "${kind}"
input_paths:
  - "${rel}"

goal: "${goal}"

constraints:
  style: "${style}"
  aspect: "${aspect}"
  resolution: "${res}"

safety:
  path_allowlist:
    - "projects/**"
    - "assets/**"
    - "renders/**"
    - "exports/**"
    - "sandbox/**"
    - "modules/studio/outputs/**"
  hard_deny:
    - "core/**"
    - "system/**"
    - "tools/**"
    - "governance/**"
    - "runtime/**"
    - ".env*"
YAML

    mv -f "$tmp" "$out"
    print -- "[studio] OK: dropped -> $out"
    print -- "RID: $rid"
    print -- "SID: $session_id"
    ;;

  chat)
    kind="${1:-}"; shift || true
    rel="${1:-}"; shift || true
    initial_goal="${1:-}"; shift || true
    [[ -n "$kind" && -n "$rel" && -n "$initial_goal" ]] || _die "chat needs: <kind> <relative_path> \"<initial_goal>\""

    print -- "[studio] Entering Interactive Session..."
    print -- "[studio] Scope: $rel"
    
    # 1. Initial Run
    output=$(ROOT="$ROOT" "$0" run "$kind" "$rel" "$initial_goal")
    sid=$(echo "$output" | grep "SID:" | cut -d' ' -f2)
    rid=$(echo "$output" | grep "RID:" | cut -d' ' -f2)
    
    print -- "[studio] SID: $sid"
    print -- "[studio] RID: $rid"

    while true; do
      print -n ">> [GMX] (type 'exit' to quit): "
      read feedback
      [[ "$feedback" == "exit" || "$feedback" == "quit" ]] && break
      [[ -z "$feedback" ]] && continue
      
      # 2. Sequential Run with session_id
      output=$(ROOT="$ROOT" "$0" run "$kind" "$rel" "$feedback" --session "$sid")
      rid=$(echo "$output" | grep "RID:" | cut -d' ' -f2)
      print -- "[studio] Sent Update: $rid"
      
      # Wait a bit for status or simulate waiting
      print -- "[studio] Waiting for iteration..."
      sleep 2
      "$0" status "$rid" || true
    done
    ;;

  status)
    rid="${1:-}"; [[ -n "$rid" ]] || _die "status needs <request_id>"
    rg -n "request_id: ${rid}" "$ROOT/modules/studio/outputs"/*/output_bundle.yaml 2>/dev/null || true
    rg -n "request_id: ${rid}" "$IFACE_EVENTS"/*.yaml 2>/dev/null || true
    ;;

  tail)
    rid="${1:-}"; [[ -n "$rid" ]] || _die "tail needs <request_id>"
    tf="$ROOT/observability/telemetry/module_studio.jsonl"
    [[ -f "$tf" ]] && tail -n 120 "$tf" | rg "$rid" || print -- "[studio] WARN: no telemetry yet (runtime not running?)"
    ;;

  promote)
    artifact="${1:-}"; shift || true
    [[ -n "$artifact" ]] || _die "promote needs <artifact_id>"
    [[ "${1:-}" == "--to" ]] || _die "promote requires --to hybrid|system"
    shift
    to_lane="${1:-}"
    [[ "$to_lane" == "hybrid" || "$to_lane" == "system" ]] || _die "--to must be hybrid or system"

    [[ -d "$ROOT/modules/studio/outputs/$artifact" ]] || _die "artifact not found: $artifact"

    pid="pro_$(_now_utc | tr -d ':-' | tr -d 'TZ' | cut -c1-14)_$(_hex8)"
    created="$(_now_utc)"

    tmp="$(mktemp "$ROOT/.tmp/studio_pro.XXXXXXXX")"
    out="$IFACE_INBOX/promotion_request_${pid}.yaml"

    cat > "$tmp" <<YAML
schema: promotion_request_v1
promotion_id: ${pid}
from_module: studio
artifact_id: ${artifact}
to_lane: ${to_lane}
author: gmx
call_sign: "[GMX]"
created_at_utc: "${created}"
YAML

    mv -f "$tmp" "$out"
    print -- "[studio] OK: promotion dropped -> $out"
    print -- "$pid"
    ;;

  help|-h|--help|"")
    _usage
    ;;

  *)
    _die "unknown command: $cmd (try: studio help)"
    ;;
esac
