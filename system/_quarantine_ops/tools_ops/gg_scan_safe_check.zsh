#!/usr/bin/env zsh
# gg_scan_safe_check.zsh — dry-run file count before running a large scan
# Usage: SOT=$HOME/02luka zsh tools/ops/gg_scan_safe_check.zsh
# Prints file count; warns if >50,000 (consider narrowing scan path).
set -euo pipefail

SOT="${SOT:-$HOME/02luka}"
echo "== DRY RUN: Counting candidate files under: $SOT =="
find "$SOT" -xdev -type f \( \
  -not -path "*/.git/*" -not -path "*/node_modules/*" -not -path "*/logs/*" \
  -not -path "*/__pycache__/*" -not -path "*/.venv/*" \
  -not -name "*.zip" -not -name "*.tar*" -not -name "*.log" \
\) | wc -l
echo "If >50,000 consider limiting scan path."
