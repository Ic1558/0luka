#!/usr/bin/env zsh
# 0luka-ZEN-AUDIT-v1.0
# Assignee: Liam (GM)

ROOT="$HOME/0luka"
AUDIT_LOG="$ROOT/observability/logs/zen_audit_$(date +%Y%m%d_%H%M%S).log"

{
  echo "=== 🔬 0luka EXECUTIVE AUDIT START: $(date) ==="
  
  echo "\n[1] STRUCTURAL ZEN CHECK (Filesystem)"
  # Find latest task file for attestation check
  LATEST_TASK=$(ls -t "$ROOT/observability/stl/tasks/open/"*.yaml 2>/dev/null | head -n 1)
  python3 "$ROOT/ops/governance/gate_runner.py" "$LATEST_TASK"
  ls -F "$ROOT"
  
  echo "\n[2] LEGACY SILENCE CHECK (Processes)"
  LEGACY_COUNT=$(ps aux | grep -Ei 'mary_dispatcher|clc_bridge|shell_watcher|02luka' | grep -v grep | wc -l)
  if [ "$LEGACY_COUNT" -eq 0 ]; then
    echo "✅ SUCCESS: All 02luka legacy processes silenced."
  else
    echo "⚠️ WARNING: $LEGACY_COUNT legacy processes detected!"
    ps aux | grep -Ei 'mary_dispatcher|clc_bridge|shell_watcher|02luka' | grep -v grep
  fi
  
  echo "\n[3] NETWORK PULSE CHECK (Port 7001)"
  if lsof -nP -iTCP:7001 -sTCP:LISTEN > /dev/null; then
    echo "✅ SUCCESS: Port 7001 (Opal-API) is breathing."
    lsof -nP -iTCP:7001 -sTCP:LISTEN
  else
    echo "❌ FAILURE: Port 7001 is down!"
  fi
  
  echo "\n[4] ONTOLOGY INTEGRITY CHECK"
  if [ -f "$ROOT/core/governance/ontology.yaml" ]; then
    echo "✅ SUCCESS: ontology.yaml version $(grep 'version:' "$ROOT/core/governance/ontology.yaml" | awk '{print $2}') found."
    shasum -a 256 "$ROOT/core/governance/ontology.yaml"
  fi
  
  echo "\n=== 🏁 AUDIT COMPLETE ==="
} | tee "$AUDIT_LOG"

echo "\n📊 Audit Report saved to: $AUDIT_LOG"
