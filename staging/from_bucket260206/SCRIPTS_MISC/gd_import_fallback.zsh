#!/usr/bin/env zsh
set -euo pipefail

SRC_BASE="$HOME/gd/02luka"
DST_BASE="/Users/icmini/LocalProjects/02luka_local_g/g"

copy_tree() {
  local rel="$1"
  local src="$SRC_BASE/$rel"
  local dst="$DST_BASE/$rel"
  echo "→ Fallback copy: $rel"
  mkdir -p "$dst"
  (cd "$src" && tar -cf - .) | (cd "$dst" && tar -xpf -)
}

# โฟลเดอร์ที่ rsync ชอบงอแงกับ Google Drive
copy_tree "docs"                || true
copy_tree "boss/templates"      || true
copy_tree "boss/deliverables"   || true
# คุณทำ symlink CLC/fyi -> CLC/commands แล้ว จัดการ commands ตรงๆ
copy_tree "CLC/commands"        || true

echo "✅ Fallback copy complete."
