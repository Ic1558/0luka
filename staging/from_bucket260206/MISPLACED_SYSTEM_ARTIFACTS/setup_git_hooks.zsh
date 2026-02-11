#!/usr/bin/env zsh

# Setup Git Hooks for 02Luka AutoSync
# สร้าง git hooks ที่จะ sync อัตโนมัติเมื่อมี commit

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

CONTAINER_PATH="/workspaces/02luka-fresh"
SYNC_SCRIPT="$HOME/sync_fresh_to_local.zsh"

echo "${BLUE}🔧 Setting up Git Hooks for 02Luka AutoSync${NC}"

# Check if we're in the right directory
if [ ! -d "$CONTAINER_PATH" ]; then
    echo "${RED}❌ Container path not found: $CONTAINER_PATH${NC}"
    echo "${YELLOW}💡 Run this script from within the VS Code container${NC}"
    exit 1
fi

# Create hooks directory
HOOKS_DIR="$CONTAINER_PATH/.git/hooks"
mkdir -p "$HOOKS_DIR"

# Create post-commit hook
cat > "$HOOKS_DIR/post-commit" << 'EOF'
#!/bin/bash
# 02Luka AutoSync - Post Commit Hook

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🔄 Git commit detected, syncing to local...${NC}"

# Run sync script if it exists
if [ -f "$HOME/sync_fresh_to_local.zsh" ]; then
    "$HOME/sync_fresh_to_local.zsh"
    echo -e "${GREEN}✅ Post-commit sync completed${NC}"
else
    echo -e "${YELLOW}⚠️  Sync script not found: $HOME/sync_fresh_to_local.zsh${NC}"
fi
EOF

# Create post-merge hook (for git pull)
cat > "$HOOKS_DIR/post-merge" << 'EOF'
#!/bin/bash
# 02Luka AutoSync - Post Merge Hook

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🔄 Git merge/pull detected, syncing to local...${NC}"

# Run sync script if it exists
if [ -f "$HOME/sync_fresh_to_local.zsh" ]; then
    "$HOME/sync_fresh_to_local.zsh"
    echo -e "${GREEN}✅ Post-merge sync completed${NC}"
else
    echo -e "${YELLOW}⚠️  Sync script not found: $HOME/sync_fresh_to_local.zsh${NC}"
fi
EOF

# Create pre-push hook (optional - sync before pushing)
cat > "$HOOKS_DIR/pre-push" << 'EOF'
#!/bin/bash
# 02Luka AutoSync - Pre Push Hook

# Colors
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🔄 Pre-push sync to ensure local is up to date...${NC}"

# Run sync script if it exists
if [ -f "$HOME/sync_fresh_to_local.zsh" ]; then
    "$HOME/sync_fresh_to_local.zsh"
else
    echo -e "${YELLOW}⚠️  Sync script not found: $HOME/sync_fresh_to_local.zsh${NC}"
fi

# Continue with push
exit 0
EOF

# Make hooks executable
chmod +x "$HOOKS_DIR/post-commit"
chmod +x "$HOOKS_DIR/post-merge"
chmod +x "$HOOKS_DIR/pre-push"

echo "${GREEN}✅ Git hooks installed successfully!${NC}"
echo ""
echo "${BLUE}📋 Installed hooks:${NC}"
echo "  • post-commit  - Sync after each commit"
echo "  • post-merge   - Sync after git pull/merge"
echo "  • pre-push     - Sync before pushing"
echo ""
echo "${YELLOW}💡 Now every git commit will automatically sync to your local Cursor path${NC}"
