#!/usr/bin/env zsh
set -euo pipefail

ROOT="$HOME/02luka"
TOOLS="$ROOT/tools"

echo "ROOT=$ROOT"
echo "TOOLS=$TOOLS"
echo

echo "Searching for snapshot banner..."
matches=()
while IFS= read -r line; do
  matches+=("$line")
done < <(grep -RIn --exclude-dir='.git' \
  -e "Antigravity System Snapshot" \
  -e "Snapshot Version" \
  -e "atg_snap" \
  "$TOOLS" 2>/dev/null || true)

if (( ${#matches[@]} == 0 )); then
  echo "❌ No matches found under $TOOLS"
  echo "Try widening search to ~/02luka (slower):"
  echo "  grep -RIn -e 'Antigravity System Snapshot' -e 'Snapshot Version' ~/02luka"
  exit 1
fi

echo "✅ Matches:"
printf '%s\n' "${matches[@]}"
echo

echo "Newest matching file (by mtime):"
files=("${(@u)${matches[@]%%:*}}")
ls -lt "${files[@]}" | head -n 20
