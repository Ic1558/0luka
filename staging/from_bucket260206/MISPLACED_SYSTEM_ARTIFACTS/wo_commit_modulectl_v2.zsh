#!/usr/bin/env zsh
set -euo pipefail

cd "$HOME/0luka"

echo "== diff =="
git diff -- core_brain/ops/modulectl.py core_brain/ops/module_registry.json || true

echo "== quick self-check =="
python3 core_brain/ops/modulectl.py validate
python3 core_brain/ops/modulectl.py status all || true
python3 core_brain/ops/modulectl.py health all || true

echo "== commit =="
git add core_brain/ops/modulectl.py core_brain/ops/module_registry.json
git commit -m "feat(ops): modulectl status/health all + reality-only registry schema v1"

echo "== push =="
git push

echo "OK"
