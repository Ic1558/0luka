#!/usr/bin/env zsh
# system/antigravity/scripts/dispatch_latest.zsh
# Purpose: Activates the most recently promoted task by moving it to the Bridge Inbox.

set -euo pipefail
setopt nullglob

ROOT="${LUKA_ROOT:-$(cd "$(dirname "$0")/../../.." && pwd)}"
PROMOTE_DIR="$ROOT/observability/antigravity_tmp/tasks"
BRIDGE_INBOX="$ROOT/artifacts/tasks/open"

# Guard
if [[ ! -d "$PROMOTE_DIR" ]]; then
    echo "❌ No promoted tasks found in $PROMOTE_DIR"
    exit 1
fi

mkdir -p "$BRIDGE_INBOX"

# Find latest task (zsh globbing: order by mod time, pick first)
LATEST_TASKS=("$PROMOTE_DIR"/task_*.md(.om))

if [[ ${#LATEST_TASKS[@]} -eq 0 ]]; then
    echo "⚠️  No tasks found in $PROMOTE_DIR to dispatch."
    exit 0
fi

TARGET_TASK="${LATEST_TASKS[1]}"
TASK_NAME="$(basename "$TARGET_TASK")"

echo "🚀 Dispatching: $TASK_NAME"
echo "   From: $PROMOTE_DIR"
echo "   To:   $BRIDGE_INBOX"

# Copy to preserve the promoted record in tmp (Receipt)
cp "$TARGET_TASK" "$BRIDGE_INBOX/$TASK_NAME"

echo "✅ Task Dispatched. Bridge should pick it up shortly."