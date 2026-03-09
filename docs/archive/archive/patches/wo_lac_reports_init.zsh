#!/usr/bin/env zsh
# wo_lac_reports_init.zsh — One-shot work-order dropper for reports init.
# ARCHIVED: Task script for WO-LAC-REPORTS-INIT-001.
set -euo pipefail
ROOT="$HOME/LocalProjects/02luka_local_g"
INBOX="$ROOT/bridge/inbox/LIAM"
mkdir -p "$INBOX"
DEST="$INBOX/WO-LAC-REPORTS-INIT-001.json"
cat > "$DEST" <<'WOJSON'
{
  "wo_id": "WO-LAC-REPORTS-INIT-001",
  "objective": "Bring system/reports into the LAC pipeline...",
  "task_spec": { "task_id": "TASK-LAC-REPORTS-INIT-001", "operations": [] }
}
WOJSON
echo "✅ Dropped WO to LIAM inbox: $DEST"
