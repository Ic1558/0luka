#!/usr/bin/env zsh
# wo_gd_canonicalize.zsh — one-shot: point ~/gd to Stream CloudStorage mount + rebuild SOT links
# ARCHIVED: one-off canonical fixup from GD migration.
set -euo pipefail

target="$HOME/Library/CloudStorage/GoogleDrive-ittipong.c@gmail.com/My Drive"
[ -e "$HOME/gd" ] && rm -rf "$HOME/gd"
ln -s "$target" "$HOME/gd"

SOT="$HOME/02luka/google_drive"
mkdir -p "$SOT"
rm -rf "$SOT/02luka_cloud"
rm -f  "$SOT/02luka" "$SOT/02luka_sync"
ln -sfn "$HOME/gd/02luka"      "$SOT/02luka"
ln -sfn "$HOME/gd/02luka_sync" "$SOT/02luka_sync"

echo "=== ~/gd ===";  ls -ld "$HOME/gd"
echo "=== SOT  ===";  ls -l "$SOT"
