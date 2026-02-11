#!/usr/bin/env zsh
set -euo pipefail

cd ~/0luka

echo "== A2.1.1 Closeout: Observability Pack =="

# 1) Staging files
echo "== Staging files =="
git add \
  plans/260205_track_a2_1_1_done.md \
  plans/opal_a2_2_identity_clock.md \
  tests/opal_a2_1_1_verify.zsh \
  tests/opal_a2_2_verify.zsh \
  runtime/apps/opal_api/common.py \
  runtime/apps/opal_api/worker.py \
  observability/telemetry/opal_events.jsonl 2>/dev/null || true

# Note: We track the jsonl file? No, usually not. But for evidence maybe?
# Let's NOT track the jsonl file in git, it's a log.
# Ensure it's ignored.
if ! grep -q "observability/telemetry/opal_events.jsonl" .gitignore 2>/dev/null; then
  echo "observability/telemetry/*.jsonl" >> .gitignore
  echo "✅ Added *.jsonl to .gitignore"
  git add .gitignore
fi

# 2) Commit + Tag
echo ""
echo "== Committing =="
git commit -m "feat(opal): A2.1.1 Observability Pack (telemetry events, jsonl logger, worker instrumentation)"

echo ""
echo "== Tagging =="
git tag -a "v0.4.0-a2.1.1" -m "OPAL A2.1.1: Observability Pack (Telemetry Events)"

echo ""
echo "✅ DONE"
git --no-pager log -1 --decorate --oneline
