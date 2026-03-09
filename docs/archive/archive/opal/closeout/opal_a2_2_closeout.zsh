#!/usr/bin/env zsh
set -euo pipefail

echo "== A2.2 Closeout: Identity + Clock Guard =="

echo "== Staging files =="
git add \
  plans/260205_track_a2_2_done.md \
  plans/opal_a2_2_identity_clock.md \
  tests/opal_a2_2_verify.zsh \
  runtime/apps/opal_api/common.py \
  runtime/apps/opal_api/worker.py -f

echo "== Committing =="
git commit -m "feat(opal): A2.2 Identity Manager & Clock Guard" || echo "No changes to commit"

echo "== Tagging =="
git tag -f -a "v0.4.0-a2.2" -m "OPAL A2.2: Federation-Ready Identity"
echo "Updated tag 'v0.4.0-a2.2'"
