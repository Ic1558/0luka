#!/usr/bin/env zsh
set -euo pipefail

cd ~/0luka

echo "== A2.1 Closeout: Staging changes =="

# 1) Ensure runtime outputs are not committed
if ! grep -q "modules/studio/outputs/" .gitignore 2>/dev/null; then
  cat >> .gitignore <<'EOF'

# OPAL runtime outputs
modules/studio/outputs/
runtime/logs/
*.log
EOF
  echo "✅ Appended .gitignore runtime rules"
fi

# 2) Move dummy_job.txt to fixtures
if [[ -f dummy_job.txt ]]; then
  mkdir -p tests/fixtures
  mv -f dummy_job.txt tests/fixtures/dummy_job.txt
  echo "✅ Moved dummy_job.txt -> tests/fixtures/"
fi

# 3) Archive stale stderr log
if [[ -f observability/logs/opal_api.stderr.log ]]; then
  mkdir -p observability/logs/_archive
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  cp -f observability/logs/opal_api.stderr.log "observability/logs/_archive/opal_api.stderr.${ts}.log" 2>/dev/null || true
  : > observability/logs/opal_api.stderr.log
  echo "✅ Archived + truncated opal_api.stderr.log"
fi

# 4) Stage files
echo ""
echo "== Staging A2.1 files =="
git add \
  plans/260205_track_a2_1_done.md \
  tests/opal_a2_1_verify.zsh \
  runtime/apps/opal_api/common.py \
  runtime/apps/opal_api/worker.py \
  .gitignore \
  tests/fixtures/dummy_job.txt 2>/dev/null || true

git add -u

# 5) Show diff (no pager)
echo ""
echo "== Staged changes (--stat) =="
git --no-pager diff --cached --stat

# 6) Commit + tag
echo ""
echo "== Committing =="
git commit -m "feat(opal): A2.1 retry policy (attempt store + backoff + atomic reclaim) + handover + verify"

echo ""
echo "== Tagging =="
git tag -a "v0.4.0-a2.1" -m "OPAL A2.1: Multi-host retry policy with atomic winner guard + backoff + output isolation"

echo ""
echo "✅ DONE - Commit + tag complete"
git --no-pager log -1 --decorate --oneline
