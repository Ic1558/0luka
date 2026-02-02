#!/bin/zsh
# cp_0luka_to_desktop.sh
# Final version: Simple, safe, and fast SOT Export.

REPO_DIR="/Users/icmini/0luka"
DEST_NAME="0luka_SOT_$(date +%Y%m%d_%H%M%S)"
DEST_PATH="$HOME/Desktop/$DEST_NAME"

echo "📦 Exporting 0luka Source of Truth to $DEST_PATH..."
mkdir -p "$DEST_PATH"

# RSYNC: Exclude heavy/hidden junk.
/usr/bin/rsync -a \
    --exclude=".git/" \
    --exclude=".venv/" \
    --exclude=".n8n/" \
    --exclude=".claude/" \
    --exclude=".gemini/" \
    --exclude="node_modules/" \
    --exclude="**/__pycache__/" \
    --exclude="logs/" \
    --exclude="observability/" \
    --exclude="artifacts/" \
    --exclude="interface/inbox/" \
    --exclude="interface/processing/" \
    --exclude="interface/done/" \
    --exclude="runtime/" \
    --exclude="workspaces/" \
    --exclude="g/" \
    "$REPO_DIR/" "$DEST_PATH/"

# Explicitly ensure .env.local is copied
if [[ -f "$REPO_DIR/.env.local" ]]; then
    cp "$REPO_DIR/.env.local" "$DEST_PATH/"
fi

echo "✅ SUCCESS: Exported to Desktop/$DEST_NAME"
