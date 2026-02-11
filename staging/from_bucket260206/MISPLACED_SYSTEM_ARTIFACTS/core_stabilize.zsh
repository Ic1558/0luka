#!/usr/bin/env zsh
set -euo pipefail

STAMP="$(date +%y%m%d_%H%M%S)"
AUDIT="$HOME/02luka/logs/wo_drop_history"
mkdir -p "$AUDIT"

echo "=== CORE STABILIZATION START $STAMP ==="

# 0) Pre-snapshot
echo "[1/7] Pre-snapshot"
"$HOME/0luka/.0luka/scripts/atg_multi_snap.zsh" > /tmp/pre_${STAMP}.txt

# 1) Kill orphan loops
echo "[2/7] Killing orphan processes"
pkill -f clc_wo_bridge_daemon.py || true
pkill -f local_truth_scan.zsh || true
pkill -f deploy_expense_pages_watch.zsh || true
pkill -f gmx_clc_orchestrator.zsh || true
pkill -f liam_engine_worker.py || true

# 2) Unload LaunchAgents
echo "[3/7] Unloading LaunchAgents"
for p in \
  com.02luka.expense_autodeploy \
  com.02luka.clc_wo_bridge \
  com.02luka.local_truth \
  com.02luka.liam_engine \
  com.02luka.mcp-memory
do
  launchctl remove "$p" 2>/dev/null || true
done

# 3) Path migration
echo "[4/7] Rewriting legacy paths"
find "$HOME/02luka" -type f \( -name "*.zsh" -o -name "*.py" -o -name "*.json" -o -name "*.plist" \) -print0 \
| xargs -0 sed -i '' 's|LocalProjects/02luka_local_g|02luka|g'

# 4) MCP memory repair
echo "[5/7] MCP memory repair"
MCP="$HOME/02luka/mcp/servers/mcp-memory"
if [[ -f "$MCP/package.json" ]]; then
  (cd "$MCP" && npm install && npm link)
else
  echo "CRITICAL: missing package.json in mcp-memory" | tee -a "$AUDIT/mcp_memory_fail_$STAMP.log"
fi

# 5) GMX syntax probe
echo "[6/7] GMX syntax probe"
GMX="$HOME/02luka/g/tools/gmx_clc_orchestrator.zsh"
if [[ -f "$GMX" ]]; then
  zsh -n "$GMX" || echo "SYNTAX ERROR: $GMX" | tee -a "$AUDIT/gmx_syntax_$STAMP.log"
fi

# 6) Post snapshot
echo "[7/7] Post-snapshot"
"$HOME/0luka/.0luka/scripts/atg_multi_snap.zsh" > /tmp/post_${STAMP}.txt

# Save audit
cp /tmp/pre_${STAMP}.txt "$AUDIT/pre_$STAMP.txt"
cp /tmp/post_${STAMP}.txt "$AUDIT/post_$STAMP.txt"

echo "=== CORE STABILIZATION COMPLETE ==="
