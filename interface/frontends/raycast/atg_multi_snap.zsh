#!/usr/bin/env zsh
# SOURCE-OF-TRUTH: $HOME/0luka/interface/frontends/raycast/atg_multi_snap.zsh
# DO NOT EDIT: managed by interface workflow
# @raycast.schemaVersion 1
# @raycast.title ATG Multi Snapshot
# @raycast.mode fullOutput
# @raycast.packageName 0luka
# @raycast.icon 📸
# @raycast.description v1.9: 0luka-only snapshot
# @raycast.needsConfirmation false

set -euo pipefail
export LC_ALL=en_US.UTF-8

# --- CONFIGURATION ---
REPOS=("/Users/icmini/0luka")
SNAP_DIR="/Users/icmini/0luka/observability/artifacts/snapshots"
mkdir -p "$SNAP_DIR"

COPY_ONLY=false
if [[ "$*" == *"--copy"* ]]; then
    COPY_ONLY=true
fi

FINAL_OUTPUT="# ATG MULTI-REPO SNAPSHOT v1.9.1\nTimestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")\n\n"

# 1. Find last snapshot for diff analysis (handle empty directory)
setopt NULL_GLOB
LAST_SNAP=$(ls -t "$SNAP_DIR"/*_snapshot.md 2>/dev/null | head -n 1 || echo "")

# --- FUNCTIONS ---
check_active_ports() {
    echo "## ACTIVE NETWORK PORTS (LISTEN) - Authoritative"
    echo '```text'
    # Use absolute path for lsof to be safe in Raycast
    /usr/sbin/lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | sort || echo "(no active ports)"
    echo '```'
}

discover_and_tail() {
    local repo_path=$1
    local search_name=$2
    # Skip .git and optimize depth
    local found_dirs=($(find "$repo_path" -maxdepth 3 -type d -name "$search_name" -not -path "*/.*" 2>/dev/null))
    
    if [[ ${#found_dirs[@]} -gt 0 ]]; then
        for dir in "${found_dirs[@]}"; do
            echo "### $search_name Path: ${dir#/Users/icmini/}"
            local files=($(ls -t "$dir"/*.{log,json,jsonl,txt}(N) 2>/dev/null | head -n 3))
            if [[ ${#files[@]} -gt 0 ]]; then
                for file in "${files[@]}"; do
                    echo "#### $(basename "$file") (last 10 lines)"
                    echo '```'
                    tail -n 10 "$file" 2>/dev/null || echo "(error reading file)"
                    echo '```'
                    echo ""
                done
            else
                echo "(no recent log files)"
                echo ""
            fi
        done
    fi
}

generate_snapshot() {
    local repo_path=$1
    [[ ! -d "$repo_path" ]] && return
    
    echo "# REPO: $(basename "$repo_path")"
    if [[ -d "$repo_path/.git" ]]; then
        # Use absolute path for git
        local branch=$(/usr/bin/git -C "$repo_path" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
        local head_sha=$(/usr/bin/git -C "$repo_path" rev-parse --short HEAD 2>/dev/null || echo "unknown")
        echo "Branch: $branch | HEAD: $head_sha"
        echo '```bash'
        /usr/bin/git -C "$repo_path" status --porcelain=v1 2>/dev/null
        echo '```'
    fi
    
    discover_and_tail "$repo_path" "telemetry"
    discover_and_tail "$repo_path" "logs"
    
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# --- EXECUTION ---
for repo in "${REPOS[@]}"; do
    FINAL_OUTPUT+="$(generate_snapshot "$repo")\n"
done

FINAL_OUTPUT+="\n$(check_active_ports)\n"
FINAL_OUTPUT+="\n## PROCESS MONITORING\n\`\`\`bash\n$(/usr/bin/pgrep -fl "mary|lac_manager|opencode|antigravity|proxy|uvicorn|opal_api|fs_watcher" 2>/dev/null || echo "(none)")\n\`\`\`\n"

# --- DIFF ANALYSIS LOGIC ---
DIFF_CONTENT=""
if [[ -f "$LAST_SNAP" ]]; then
    NEW_TEMP_FILE=$(mktemp)
    printf "%b" "$FINAL_OUTPUT" > "$NEW_TEMP_FILE"
    
    # Extract meaningful changes (exclude timestamp lines)
    DIFF_RESULT=$(diff -u "$LAST_SNAP" "$NEW_TEMP_FILE" 2>/dev/null | grep -E "^\+|^\-" | grep -vE "^\+\+\+|^\-\-\-|Timestamp" | head -n 20 || echo "No significant changes.")
    
    DIFF_CONTENT="\n## 🛡️ DIFF ANALYSIS (Changes since $(basename "$LAST_SNAP"))\n"
    DIFF_CONTENT+='```diff\n'
    DIFF_CONTENT+="$DIFF_RESULT\n"
    DIFF_CONTENT+='```\n'
    rm -f "$NEW_TEMP_FILE"
fi

FINAL_OUTPUT+="$DIFF_CONTENT"

# --- AUTO-SAVE & DELIVERY ---
NEW_SNAP_PATH="$SNAP_DIR/$(date +"%y%m%d_%H%M%S")_snapshot.md"
printf "%b" "$FINAL_OUTPUT" > "$NEW_SNAP_PATH"

# Output to console if NOT in copy_only mode
if [[ "$COPY_ONLY" == "false" ]]; then
    printf "%b" "$FINAL_OUTPUT"
fi

# Clipboard delivery (hardened)
printf "%b" "$FINAL_OUTPUT" | /usr/bin/pbcopy 2>/dev/null || true
printf "%b" "$FINAL_OUTPUT" | /usr/bin/osascript -e 'set the clipboard to (read (POSIX file "/dev/stdin") as «class utf8»)' 2>/dev/null || true

if [[ "$COPY_ONLY" == "false" ]]; then
    echo "\n✅ v1.9.1 Complete: Snapshot saved to $(basename "$NEW_SNAP_PATH") and copied to clipboard."
else
    echo "✅ Snapshot v1.9.1 copied to clipboard."
fi

# --- PHASE D: REMEDIATION TRIGGER ---
if [[ -f "$HOME/0luka/tools/remediator.py" ]]; then
    echo "[GOVERNANCE] Triggering remediation analysis..."
    python3 "$HOME/0luka/tools/remediator.py" "$NEW_SNAP_PATH" 2>/dev/null || true
fi

# --- PHASE E: CANARY ALERT (Circuit Breaker) ---
if [[ -f "$HOME/0luka/tools/canary_alert.py" ]]; then
    python3 "$HOME/0luka/tools/canary_alert.py" 2>/dev/null || true
fi
