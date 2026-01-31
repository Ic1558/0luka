#!/usr/bin/env zsh
set -euo pipefail
setopt nullglob

# --- CONFIGURATION & GUARDS ---
# Resolve Root from script location: system/antigravity/scripts/ -> ../../../
ROOT="${LUKA_ROOT:-$(cd "$(dirname "$0")/../../.." && pwd)}"
TARGET_ROOT="$ROOT/observability/antigravity_tmp"

# Guard: Target must be inside repo structure
if [[ "$TARGET_ROOT" != "$ROOT/observability/"* ]]; then
    echo "❌ FATAL: Safety lock. Target must be inside observability/."
    exit 1
fi

BRAIN_BASE="${HOME}/.gemini/antigravity/brain"

# --- BRAIN DETECTION (Fail Hard) ---
if [[ -n "${GEMINI_BRAIN_ID:-}" ]]; then
    BRAIN_DIR="${BRAIN_BASE}/${GEMINI_BRAIN_ID}"
    if [[ ! -d "$BRAIN_DIR" ]]; then
        echo "❌ FATAL: Specified brain ID not found: $BRAIN_DIR"
        exit 2
    fi
else
    # Auto-detect latest brain session (zsh: dirs, order by mod time)
    BRAIN_CANDIDATES=("${BRAIN_BASE}/"*(/om))
    if [[ ${#BRAIN_CANDIDATES[@]} -eq 0 ]]; then
        echo "❌ FATAL: No brain sessions found in $BRAIN_BASE. Cannot auto-detect."
        exit 2
    fi
    BRAIN_DIR="${BRAIN_CANDIDATES[1]}"
fi

BRAIN_ID="$(basename "$BRAIN_DIR")"
SHORT_ID="${BRAIN_ID:0:8}"
echo "Using Brain Source: $BRAIN_DIR ($SHORT_ID)"

# --- TIMESTAMP (UTC) ---
TIMESTAMP="$(date -u +%Y%m%d_%H%M%S)"
TS_ISO="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# Ensure target dirs (redundant if retention script ran, but safe)
mkdir -p "${TARGET_ROOT}/tasks" "${TARGET_ROOT}/implementation_plan" "${TARGET_ROOT}/phase_reports" "${TARGET_ROOT}/walkthrough"

# Track promoted files for manifest
PROMOTED_JSON_ITEMS=()

# Helper: Atomic Promote
promote() {
    local src_name="$1"
    local dest_rel="$2"
    local src_path="$BRAIN_DIR/$src_name"
    local dest_path="$TARGET_ROOT/$dest_rel"

    if [[ -f "$src_path" ]]; then
        mkdir -p "$(dirname "$dest_path")"
        local tmp="${dest_path}.tmp"
        cp "$src_path" "$tmp"
        mv -f "$tmp" "$dest_path"
        
        echo "✅ Promoted: $src_name -> $dest_rel"
        PROMOTED_JSON_ITEMS+=("{\"src\": \"$src_name\", \"dst\": \"$dest_rel\"}")
    fi
}

# --- EXECUTION ---

# 1. Standard Files
promote "task.md" "tasks/task_${SHORT_ID}_${TIMESTAMP}.md"
promote "implementation_plan.md" "implementation_plan/plan_${SHORT_ID}_${TIMESTAMP}.md"
promote "walkthrough.md" "walkthrough/walkthrough_${SHORT_ID}_${TIMESTAMP}.md"

# 2. Glob Patterns (OnePagers, GRs)
for f in "${BRAIN_DIR}"/Handover_OnePager*.md "${BRAIN_DIR}"/GR_*.md; do
    [[ -f "$f" ]] || continue
    base=$(basename "$f")
    promote "$base" "phase_reports/${base%.md}_${SHORT_ID}_${TIMESTAMP}.md"
done

# 3. Generate Manifest
MANIFEST_FILE="${TARGET_ROOT}/promote_manifest_${TIMESTAMP}.json"
# Join array with commas
ITEMS_STR="$(IFS=,; echo "${PROMOTED_JSON_ITEMS[*]}")"

cat <<JSON > "$MANIFEST_FILE"
{
  "schema": "promote_manifest.v1",
  "ts_utc": "$TS_ISO",
  "brain_id": "$BRAIN_ID",
  "brain_dir": "$BRAIN_DIR",
  "promoted": [ $ITEMS_STR ]
}
JSON

echo "📜 Manifest written: $MANIFEST_FILE"
echo "Done. Artifacts secured in 0luka Store."
