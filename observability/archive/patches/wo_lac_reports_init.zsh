#!/usr/bin/env zsh
set -euo pipefail

ROOT="$HOME/LocalProjects/02luka_local_g"
AGENT="LIAM"
INBOX="$ROOT/bridge/inbox/$AGENT"
HISTORY="$ROOT/logs/wo_drop_history"
TMPDIR="$ROOT/tmp"

mkdir -p "$INBOX" "$HISTORY" "$TMPDIR"

TMP_JSON="$(mktemp "$TMPDIR/WO-LAC-REPORTS-INIT-XXXXXX.json")"

cat > "$TMP_JSON" <<'WOJSON'
{
  "wo_id": "WO-LAC-REPORTS-INIT-001",
  "objective": "Bring system/reports into the LAC pipeline as a first-class project, mirroring the Antigravity pattern: 1) treat system/reports as the real project root, 2) create (or verify) a clean symlink g/src/reports -> system/reports, 3) add a minimal LAC-oriented README under system/reports/, 4) add a minimal pytest smoke test under system/reports/tests/ that only asserts the project layout (no business logic), and 5) keep all changes policy-compliant via shared.policy (no touching other projects).",
  "routing_hint": "dev_oss",
  "priority": "normal",
  "complexity": "simple",
  "self_apply": true,
  "requires_paid_lane": false,
  "task_spec": {
    "task_id": "TASK-LAC-REPORTS-INIT-001",
    "operations": []
  }
}
WOJSON

DEST="$INBOX/WO-LAC-REPORTS-INIT-001.json"

cp "$TMP_JSON" "$HISTORY/WO-LAC-REPORTS-INIT-001.json"
mv "$TMP_JSON" "$DEST"

echo "✅ Dropped WO to LIAM inbox:"
echo "   $DEST"
echo
echo "📂 Current inbox contents:"
ls -l "$INBOX"
