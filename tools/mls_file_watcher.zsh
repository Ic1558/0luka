#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
ROOT="${ROOT%/}"
export ROOT
ROOT_REF='${ROOT}'
OBS="$ROOT/observability"
OBS_REF="${ROOT_REF}/observability"
cd "$ROOT"

# Watch root: agents directories (example)
WATCH_ROOT="$ROOT/agents"
WATCH_ROOT_REF="${ROOT_REF}/agents"
mkdir -p "$WATCH_ROOT"

# Determine mode
if command -v fswatch >/dev/null 2>&1; then
    MODE="fswatch"
else
    MODE="manual_test"
fi

run_cycle() {
    local TRIGGER_PATH="$1"
    local TRIGGER_PATH_REF="$TRIGGER_PATH"
    if [[ "$TRIGGER_PATH" == "$ROOT/"* ]]; then
        TRIGGER_PATH_REF="${ROOT_REF}/${TRIGGER_PATH#$ROOT/}"
    fi
    
    TS="$(date -u +%Y%m%dT%H%M%SZ)"
    OUT_DIR="$OBS/artifacts/mls"
    TASK_DIR="$OBS/quarantine/tasks"
    TEL_DIR="$OBS/telemetry"
    
    OUT_JSON="$OUT_DIR/${TS}_mls_event.json"
    TEL_JSON="$TEL_DIR/mls_file_watcher.latest.json"
    TASK_YAML="$TASK_DIR/${TS}_mls.task.yaml"
    OUT_JSON_REF="$OBS_REF/artifacts/mls/${TS}_mls_event.json"
    TEL_JSON_REF="$OBS_REF/telemetry/mls_file_watcher.latest.json"

    # Minimal Artifact
    cat > "$OUT_JSON" <<JSON
{
  "ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "module": "mls_file_watcher",
  "event_type": "filesystem_change",
  "path": "$TRIGGER_PATH_REF",
  "mode": "$MODE"
}
JSON

    # Telemetry Breadcrumb
    cp "$OUT_JSON" "$TEL_JSON"
    
    # SHA256
    SHA="$(shasum -a 256 "$OUT_JSON" | awk '{print $1}')"

    # TaskSpec v1.0
    cat > "$TASK_YAML" <<YAML
actor: module.mls_file_watcher
intent: action.mls.watch
meta:
  ts_utc: "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  host: "$(hostname)"
artifacts:
  outputs:
    - path: "$OUT_JSON_REF"
      sha256: "$SHA"
verification:
  gates:
    - gate.fs.purity
    - gate.hash.match
    - gate.proc.clean
YAML

    # Router Call (Note: core_kernel/router.py was quarantined)
    # python3 "$ROOT/ops/core_kernel/router.py" "$TASK_YAML"
    echo "OK: processed event for $TRIGGER_PATH_REF"
}

if [[ "$MODE" == "fswatch" ]] && [[ "${1:-}" != "--oneshot" ]]; then
    echo "Starting fswatch on $WATCH_ROOT_REF..."
    # Simple loop: excludes dotfiles, debounces slightly by read loop nature
    fswatch -0 -r -l 1 --exclude "/\." "$WATCH_ROOT" | while read -d "" event; do
        run_cycle "$event"
    done
else
    # Manual / One-shot mode
    echo "Running one-shot check..."
    TEST_FILE="$WATCH_ROOT/test_mls_trigger.txt"
    touch "$TEST_FILE"
    run_cycle "$TEST_FILE"
    rm "$TEST_FILE"
fi
