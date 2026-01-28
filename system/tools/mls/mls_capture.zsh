#!/usr/bin/env zsh
# MLS (Machine Learning System) - Capture Lessons Learned
# Auto-triggered after system improvements, solutions, or failures
set -euo pipefail

ROOT="${ROOT:-${LUKA_SOT:-${HOME}/0luka}}"
MLS_DB="${MLS_DB:-$ROOT/g/knowledge/mls_lessons.jsonl}"
MLS_INDEX="${MLS_INDEX:-$ROOT/g/knowledge/mls_index.json}"
MLS_DIR="$(dirname "$MLS_DB")"

die() {
  echo "❌ $*" >&2
  exit 1
}

warn() {
  echo "⚠️  $*" >&2
}

command -v jq >/dev/null 2>&1 || die "jq is required but not found in PATH"
mkdir -p "$MLS_DIR" || die "Failed to create MLS directory: $MLS_DIR"
if [[ -e "$MLS_DB" && ! -w "$MLS_DB" ]]; then
  die "MLS database not writable: $MLS_DB"
fi

# Usage: mls_capture.zsh <type> <title> <description> [context]
# Types: solution, failure, improvement, pattern, antipattern

TYPE="${1:-}"
TITLE="${2:-}"
DESC="${3:-}"
CONTEXT="${4:-}"

if [[ -z "$TYPE" ]] || [[ -z "$TITLE" ]] || [[ -z "$DESC" ]]; then
  cat <<USAGE
Usage: mls_capture.zsh <type> <title> <description> [context]

Types:
  solution     - Something that worked well
  failure      - Something that failed (learn from it)
  improvement  - System enhancement made
  pattern      - Successful pattern discovered
  antipattern  - Anti-pattern to avoid

Examples:
  mls_capture.zsh solution "GD Sync Setup" "Two-phase automated deployment worked perfectly" "Phase1+Phase2 with conflict resolution"

  mls_capture.zsh failure "Direct GD Merge" "Merging 89GB+6.5GB GD folders was too complex" "Different structures, chose fresh start instead"

  mls_capture.zsh pattern "Archive with README" "Always create README when archiving large files" "89GB diagnostics with 60-day review plan"

USAGE
  exit 1
fi

case "$TYPE" in
  solution|failure|improvement|pattern|antipattern) ;;
  *) die "Invalid type: $TYPE (expected solution|failure|improvement|pattern|antipattern)" ;;
esac

# Generate lesson ID
TIMESTAMP=$(date +%s)
LESSON_ID="MLS-${TIMESTAMP}"

# Capture current context
CURRENT_WO=$(ls -t ${ROOT}/observability/bridge/inbox/*/WO-*.zsh(N) 2>/dev/null | head -1 | xargs basename 2>/dev/null || echo "none")
CURRENT_SESSION=$(ls -t ${ROOT}/g/reports/sessions/*.md(N) 2>/dev/null | head -1 | xargs basename 2>/dev/null || echo "none")

# Create lesson entry
if ! LESSON=$(jq -n \
  --arg id "$LESSON_ID" \
  --arg type "$TYPE" \
  --arg title "$TITLE" \
  --arg desc "$DESC" \
  --arg context "$CONTEXT" \
  --arg wo "$CURRENT_WO" \
  --arg session "$CURRENT_SESSION" \
  --arg ts "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  '{
    id: $id,
    type: $type,
    title: $title,
    description: $desc,
    context: $context,
    related_wo: $wo,
    related_session: $session,
    timestamp: $ts,
    tags: [],
    verified: false,
    usefulness_score: 0,
    source: "manual"
  }'); then
  die "Failed to build lesson entry (jq error)"
fi

# Append to database
if ! printf '%s\n' "$LESSON" >> "$MLS_DB"; then
  die "Failed to append to MLS database: $MLS_DB"
fi

# Update index
if [[ -f "$MLS_INDEX" ]]; then
  if ! INDEX=$(jq -e '.' "$MLS_INDEX" 2>/dev/null); then
    warn "MLS index invalid; backing up and recreating"
    mv "$MLS_INDEX" "$MLS_INDEX.bak.$TIMESTAMP" 2>/dev/null || true
    INDEX='{"total":0,"by_type":{},"last_updated":""}'
  fi
else
  INDEX='{"total":0,"by_type":{},"last_updated":""}'
fi

# Increment counts
if ! NEW_INDEX=$(echo "$INDEX" | jq \
  --arg type "$TYPE" \
  --arg ts "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
  '.total += 1 | .by_type[$type] = (.by_type[$type] // 0) + 1 | .last_updated = $ts'); then
  die "Failed to update MLS index (jq error)"
fi

if ! printf '%s\n' "$NEW_INDEX" > "$MLS_INDEX"; then
  die "Failed to write MLS index: $MLS_INDEX"
fi

# Output
echo "✅ Lesson captured: $LESSON_ID"
echo "   Type: $TYPE"
echo "   Title: $TITLE"
echo ""
echo "📊 MLS Stats:"
if ! echo "$NEW_INDEX" | jq -r '
  "   Total lessons: \(.total)",
  "   By type:",
  (.by_type | to_entries[] | "     - \(.key): \(.value)")
'; then
  warn "Failed to render MLS stats from index JSON"
fi

# Trigger R&D autopilot notification
if [[ -d "$ROOT/observability/bridge/inbox/rd" ]]; then
  RD_NOTIFICATION="$ROOT/observability/bridge/inbox/rd/MLS-notification-${TIMESTAMP}.json"
  if jq -n \
      --arg lesson_id "$LESSON_ID" \
      --arg type "$TYPE" \
      --arg title "$TITLE" \
      '{
        task: "review_mls_lesson",
        lesson_id: $lesson_id,
        lesson_type: $type,
        title: $title,
        priority: "P3",
        auto_approve: true
      }' > "$RD_NOTIFICATION"; then
    echo "🔔 Notified R&D autopilot"
  else
    warn "Failed to write R&D notification: $RD_NOTIFICATION"
  fi
fi

echo ""
echo "📚 View all lessons:"
echo "   cat $MLS_DB | jq"
echo ""
echo "🔍 Search lessons:"
echo "   $ROOT/system/tools/mls/mls_search.zsh <keyword>"
