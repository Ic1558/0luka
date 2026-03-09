#!/usr/bin/env zsh
# setup_git_hooks.zsh — Install Git hooks for 02Luka AutoSync
# usage: zsh tools/git/setup_git_hooks.zsh
set -euo pipefail

# Config
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo $PWD)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"
SYNC_SCRIPT="$HOME/sync_fresh_to_local.zsh"

echo "🔧 Setting up Git Hooks for 02Luka AutoSync..."

if [ ! -d "$HOOKS_DIR" ]; then
    echo "❌ Git hooks directory not found: $HOOKS_DIR"
    exit 1
fi

# 1) post-commit
cat > "$HOOKS_DIR/post-commit" << EOF
#!/bin/bash
# 02Luka AutoSync - Post Commit Hook
echo "🔄 Git commit detected, syncing to local..."
if [ -f "$SYNC_SCRIPT" ]; then
    "$SYNC_SCRIPT"
    echo "✅ Post-commit sync completed"
else
    echo "⚠️  Sync script not found: $SYNC_SCRIPT"
fi
EOF

# 2) post-merge (for git pull)
cat > "$HOOKS_DIR/post-merge" << EOF
#!/bin/bash
# 02Luka AutoSync - Post Merge Hook
echo "🔄 Git merge/pull detected, syncing to local..."
if [ -f "$SYNC_SCRIPT" ]; then
    "$SYNC_SCRIPT"
    echo "✅ Post-merge sync completed"
else
    echo "⚠️  Sync script not found: $SYNC_SCRIPT"
fi
EOF

# 3) pre-push
cat > "$HOOKS_DIR/pre-push" << EOF
#!/bin/bash
# 02Luka AutoSync - Pre Push Hook
echo "🔄 Pre-push sync to ensure local is up to date..."
if [ -f "$SYNC_SCRIPT" ]; then
    "$SYNC_SCRIPT"
fi
exit 0
EOF

# Make executable
chmod +x "$HOOKS_DIR/post-commit" "$HOOKS_DIR/post-merge" "$HOOKS_DIR/pre-push"

echo "✅ Git hooks installed successfully!"
echo "  • post-commit  - Sync after each commit"
echo "  • post-merge   - Sync after git pull/merge"
echo "  • pre-push     - Sync before pushing"
echo ""
echo "💡 Every commit will now automatically trigger $SYNC_SCRIPT"
