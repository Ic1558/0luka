#!/usr/bin/env zsh
set -euo pipefail

GD_BASE="$HOME/Library/CloudStorage/GoogleDrive-ittipong.c@gmail.com/My Drive/02luka"

echo ">>> Scanning for symlinks at depth 1 in: $GD_BASE"
if [[ ! -d "$GD_BASE" ]]; then
  echo "ERROR: GD base not found"; exit 1
fi

# Zsh Native way to find and process links
LINKS=($(find "$GD_BASE" -maxdepth 1 -mindepth 1 -type l 2>/dev/null || true))

if (( ${#LINKS[@]} == 0 )); then
  echo "• No symlinks found at depth 1. ✅ CLEAN"
  exit 0
fi

echo "• Found symlinks. Replacing with empty real folders:"
for l in "${LINKS[@]}"; do
  name="$(basename "$l")"
  echo "  • Found Symlink: $name"
  # 1. Force remove the symlink
  rm -rf "$l"
  # 2. Recreate as real directory, forcing parent directory creation (though parent exists)
  mkdir -p "$GD_BASE/$name"
  echo "  • Replaced $name with real directory."
done
