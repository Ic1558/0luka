#!/usr/bin/env zsh

# 02Luka Container → Local Sync Script
# สำหรับ sync ข้อมูลจาก container ไปยัง Cursor local path

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Paths
CONTAINER_PATH="/workspaces/02luka-fresh"
LOCAL_PATH="$HOME/LocalProjects/02luka_local_g/g"

echo "${BLUE}🔄 02Luka Container → Local Sync${NC}"
echo "${YELLOW}From:${NC} $CONTAINER_PATH"
echo "${YELLOW}To:${NC}   $LOCAL_PATH"
echo ""

# Check if container path exists
if [ ! -d "$CONTAINER_PATH" ]; then
    echo "${RED}❌ Container path not found: $CONTAINER_PATH${NC}"
    echo "${YELLOW}💡 Make sure you're running this from VS Code container or the path is correct${NC}"
    exit 1
fi

# Create local directory if it doesn't exist
mkdir -p "$LOCAL_PATH"

# Sync with rsync
echo "${BLUE}📦 Syncing files...${NC}"
rsync -av --delete \
  "$CONTAINER_PATH/" \
  "$LOCAL_PATH/" \
  --exclude '.git' \
  --exclude 'node_modules' \
  --exclude '.devcontainer' \
  --exclude '.cache' \
  --exclude '.vscode-server' \
  --exclude '.next' \
  --exclude 'dist' \
  --exclude 'build' \
  --exclude 'coverage' \
  --exclude '.nyc_output' \
  --exclude '*.log' \
  --exclude '.DS_Store' \
  --exclude 'Thumbs.db'

echo ""
echo "${GREEN}✅ Sync completed successfully!${NC}"
echo "${YELLOW}📁 Cursor can now access the full repo at: $LOCAL_PATH${NC}"

# Show sync summary
echo ""
echo "${BLUE}📊 Sync Summary:${NC}"
echo "  • Source: Container ($CONTAINER_PATH)"
echo "  • Destination: Local ($LOCAL_PATH)"
echo "  • Excluded: .git, node_modules, .devcontainer, .cache, .vscode-server"
echo "  • Ready for Cursor AI/Codex/MCP usage"
