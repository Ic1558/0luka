#!/usr/bin/env zsh
set -euo pipefail
cd "$HOME/02luka"
OUT_ALL="$HOME/Desktop/rg_refs_$(date +%Y%m%d_%H%M%S).txt"
OUT_SPLIT="$HOME/Desktop/rg_refs_split_$(date +%Y%m%d_%H%M%S).txt"
PAT="LocalProjects/02luka_local_g"
echo "== Full scan -> $OUT_ALL =="
rg -n "$PAT" . -S --hidden --no-messages --threads 2 \
  --max-filesize 2M \
  -g '!**/.git/**' -g '!**/.venv/**' -g '!**/node_modules/**' \
  -g '!**/_import_logs/**' -g '!**/archive/**' > "$OUT_ALL" || true
echo "== Split scan -> $OUT_SPLIT =="
rm -f "$OUT_SPLIT"
for D in bridge g gci run logs wo snapshots docs; do
  echo "## $D" | tee -a "$OUT_SPLIT"
  rg -n "$PAT" "$D" -S --hidden --no-messages --threads 2 \
    --max-filesize 2M \
    -g '!**/.git/**' -g '!**/.venv/**' -g '!**/node_modules/**' \
    -g '!**/_import_logs/**' -g '!**/archive/**' \
    | tee -a "$OUT_SPLIT" || true
done
echo "Saved: $OUT_ALL"
echo "Saved: $OUT_SPLIT"
