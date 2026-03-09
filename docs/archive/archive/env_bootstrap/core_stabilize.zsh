#!/usr/bin/env zsh
# core_stabilize.zsh — one-shot: kill orphan processes, unload stuck LaunchAgents,
#                      rewrite legacy paths, repair MCP memory, run GMX probe.
# ARCHIVED: bulk incident stabilizer from OPAL migration era. Already applied.
set -euo pipefail

STAMP="$(date +%y%m%d_%H%M%S)"
AUDIT="$HOME/02luka/logs/wo_drop_history"
mkdir -p "$AUDIT"

echo "=== CORE STABILIZATION START $STAMP ==="

echo "[1/7] Pre-snapshot"
"$HOME/0luka/.0luka/scripts/atg_multi_snap.zsh" > /tmp/pre_${STAMP}.txt

echo "[2/7] Killing orphan processes"
pkill -f clc_wo_bridge_daemon.py || true
pkill -f local_truth_scan.zsh || true
pkill -f deploy_expense_pages_watch.zsh || true
pkill -f gmx_clc_orchestrator.zsh || true
pkill -f liam_engine_worker.py || true

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

echo "[4/7] Rewriting legacy paths"
find "$HOME/02luka" -type f \( -name "*.zsh" -o -name "*.py" -o -name "*.json" -o -name "*.plist" \) -print0 \
| xargs -0 sed -i '' 's|LocalProjects/02luka_local_g|02luka|g'

echo "[5/7] MCP memory repair"
MCP="$HOME/02luka/mcp/servers/mcp-memory"
if [[ -f "$MCP/package.json" ]]; then
  (cd "$MCP" && npm install && npm link)
else
  echo "CRITICAL: missing package.json in mcp-memory" | tee -a "$AUDIT/mcp_memory_fail_$STAMP.log"
fi

echo "[6/7] GMX syntax probe"
GMX="$HOME/02luka/g/tools/gmx_clc_orchestrator.zsh"
if [[ -f "$GMX" ]]; then
  zsh -n "$GMX" || echo "SYNTAX ERROR: $GMX" | tee -a "$AUDIT/gmx_syntax_$STAMP.log"
fi

echo "[7/7] Post-snapshot"
"$HOME/0luka/.0luka/scripts/atg_multi_snap.zsh" > /tmp/post_${STAMP}.txt

cp /tmp/pre_${STAMP}.txt "$AUDIT/pre_$STAMP.txt"
cp /tmp/post_${STAMP}.txt "$AUDIT/post_$STAMP.txt"

echo "=== CORE STABILIZATION COMPLETE ==="
