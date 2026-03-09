#!/usr/bin/env zsh
# wo_commit_modulectl_v2.zsh — Validate and commit Modulectl v2 fix.
# ARCHIVED: One-shot task helper.
set -euo pipefail
cd "$HOME/0luka"
python3 core_brain/ops/modulectl.py validate
git add core_brain/ops/modulectl.py core_brain/ops/module_registry.json
git commit -m "feat(ops): modulectl status/health all + reality-only registry schema v1"
git push
echo "OK"
