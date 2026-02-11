#!/usr/bin/env zsh
set -euo pipefail

cd ~/0luka

echo "== git status (before) =="
git status --porcelain

# 1) Ensure runtime outputs are not committed (recommend ignore)
# NOTE: adjust paths if you already have .gitignore rules
if ! rg -q "modules/studio/outputs/" .gitignore 2>/dev/null; then
  cat >> .gitignore <<'EOF'

# OPAL runtime outputs
modules/studio/outputs/
runtime/logs/
*.log
EOF
  echo "OK: appended .gitignore runtime rules"
fi

# 2) If dummy_job.txt is meant as fixture, move it (optional)
if [[ -f dummy_job.txt ]]; then
  mkdir -p tests/fixtures
  mv -f dummy_job.txt tests/fixtures/dummy_job.txt
  echo "OK: moved dummy_job.txt -> tests/fixtures/dummy_job.txt"
fi

# 3) Rotate/truncate stale stderr log (optional but recommended)
# Keep a copy under plans/evidence if you want.
if [[ -f observability/logs/opal_api.stderr.log ]]; then
  mkdir -p observability/logs/_archive
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  cp -f observability/logs/opal_api.stderr.log "observability/logs/_archive/opal_api.stderr.${ts}.log" || true
  : > observability/logs/opal_api.stderr.log
  echo "OK: archived + truncated observability/logs/opal_api.stderr.log"
fi

echo "== git status (after hygiene) =="
git status --porcelain

# 4) Stage only what we want
git add \
  plans/260205_track_a2_1_done.md \
  tests/opal_a2_1_verify.zsh \
  runtime/apps/opal_api/common.py \
  runtime/apps/opal_api/worker.py \
  runtime/apps/opal_api/opal_api_server.py \
  .gitignore \
  tests/fixtures/dummy_job.txt 2>/dev/null || true

# Also include whiteboard legacy move if present
git add system/tools/whiteboard/_legacy 2>/dev/null || true
git add -u

echo "== diff (staged) =="
git diff --cached --stat

# 5) Commit + tag
git commit -m "feat(opal): A2.1 retry policy (attempt store + backoff + atomic reclaim) + handover + verify"

git tag -a "v0.4.0-a2.1" -m "OPAL A2.1: Multi-host retry policy with atomic winner guard + backoff + output isolation"

echo "DONE ✅  Commit + tag complete."
git --no-pager log -1 --decorate
