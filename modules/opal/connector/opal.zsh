#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
MODULE="opal"
INBOX="$ROOT/modules/opal/inbox"
STUDIO_INBOX="$ROOT/modules/studio/inbox"

# Ensure dirs
mkdir -p "$INBOX" "$STUDIO_INBOX"

_usage() {
  cat <<'EOF'
opal.zsh — OPAL Hybrid Lane Connector
Authorized bridge for Google Opal automation.

Commands:
  opal run <url> "<task>"      -> Executes automation immediately (Trusted)
  opal handoff <artifact>      -> Fast-tracks result to Studio Lane

Note: This lane runs with HIGH TRUST. It does not wait for user confirmation.
EOF
}

cmd="${1:-}"; shift || true
case "$cmd" in
  run)
    url="${1:?URL required}"
    task="${2:?Task required}"
    
    # Create Task File
    ts=$(date -u +"%Y%m%dT%H%M%SZ")
    id="opal_task_${ts}"
    task_file="$INBOX/${id}.yaml"
    
    cat > "$task_file" <<YAML
schema: opal_task_v1
id: ${id}
url: "${url}"
task: "${task}"
status: PENDING
auth_scope: browser_control
YAML
    echo "[opal] Task queued: $task_file"
    
    # Execute Driver Immediately (Authorized Autonomous Mode)
    echo "[opal] Launching Authorized Agent (Playwright)..."
    python3 "$ROOT/modules/opal/agent/opal_driver.py" "$task_file"
    ;;
    
  handoff)
    artifact="${1:?Artifact path required}"
    if [[ ! -f "$artifact" ]]; then
        echo "[opal] Error: Artifact not found: $artifact"
        exit 1
    fi
    
    # Fast-track logic: Move directly to Studio inbox with "trusted" signature
    name=$(basename "$artifact")
    cat > "$STUDIO_INBOX/trusted_${name}.yaml" <<YAML
schema: studio_import_v1
source: opal_lane
trust: verified
artifact_path: "${artifact}"
original_task: "system_handoff"
YAML
    echo "[opal] Fast-track handoff complete: $STUDIO_INBOX/trusted_${name}.yaml"
    ;;
    
  *)
    _usage
    ;;
esac
