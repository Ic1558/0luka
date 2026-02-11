#!/usr/bin/env zsh
set -euo pipefail
SOT="$HOME/02luka"
echo "== DRY RUN: Counting candidate files for scan =="
find "$SOT" -xdev -type f \( \
  -not -path "*/.git/*" -not -path "*/node_modules/*" -not -path "*/logs/*" \
  -not -path "*/__pycache__/*" -not -path "*/.venv/*" \
  -not -name "*.zip" -not -name "*.tar*" -not -name "*.log" \
\) | wc -l
echo "If >50,000 consider limiting scan path."
