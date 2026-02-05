#!/usr/bin/env zsh
set -euo pipefail

print_h(){ echo; echo "=== $1 ==="; }

# 1) ค้นหา "My Drive" แบบไดนามิก (หลายความเป็นไปได้)
candidates=(
  "$HOME/My Drive"
  "$HOME/Google Drive/My Drive"
  "$HOME/Library/CloudStorage"/*/"My Drive"
)

found_root=""
for c in "${candidates[@]}"; do
  for p in ${(M)~c:#*}; do
    if [[ -d "$p" ]]; then
      found_root="$p"
      break
    fi
  done
  [[ -n "$found_root" ]] && break
done

# สำรอง: ใช้ Spotlight หาโฟลเดอร์ชื่อ "My Drive"
if [[ -z "$found_root" ]] && command -v mdfind >/dev/null 2>&1; then
  guess="$(mdfind "kMDItemFSName == 'My Drive'cd && kMDItemPath == '$HOME/*'" | head -n 1)"
  [[ -n "$guess" && -d "$guess" ]] && found_root="$guess"
fi

# 2) สรุป path
if [[ -z "$found_root" ]]; then
  echo "❌ ไม่พบโฟลเดอร์ 'My Drive' ภายใน $HOME"; exit 1
fi

GD_ROOT="$found_root"
GD_02LUKA="$GD_ROOT/02luka"

print_h "Resolved Google Drive Roots"
echo "GD_ROOT   : $GD_ROOT"
echo "GD_02LUKA : $GD_02LUKA"

# 3) ยืนยัน 02luka มีจริง (Mirror อาจยังโหลดไม่ครบก็ได้)
if [[ ! -d "$GD_02LUKA" ]]; then
  echo "⚠️ ยังไม่พบ '$GD_02LUKA' (อาจกำลัง mirror อยู่)"; 
  # ไม่ exit เพื่อให้ export ตัวแปรแปะไว้ใช้ก่อน
fi

# 4) Export ให้ชั่วคราวใน shell นี้
export LUKA_GD_ROOT="$GD_ROOT"
export LUKA_GD_BASE="$GD_02LUKA"

# 5) เพิ่มลง ~/.zshrc ถ้ายังไม่มี (มาตรฐานเดียวใช้ต่อทุกสคริปต์)
ensure_line() {
  local line="$1"
  grep -Fqs "$line" "$HOME/.zshrc" || echo "$line" >> "$HOME/.zshrc"
}
ensure_line ''
ensure_line '# 02luka: Google Drive dynamic paths'
ensure_line 'export LUKA_GD_ROOT="${LUKA_GD_ROOT:-$HOME/Library/CloudStorage/*/My Drive}"'
ensure_line 'export LUKA_GD_BASE="${LUKA_GD_BASE:-$LUKA_GD_ROOT/02luka}"'

print_h "Ready to use"
echo "ใช้ตัวแปรมาตรฐานได้ทันที:"
echo "  - \$LUKA_GD_ROOT = $LUKA_GD_ROOT"
echo "  - \$LUKA_GD_BASE = $LUKA_GD_BASE"
echo
echo "ตัวอย่างตรวจสอบ:"
echo "  du -sh \"$LUKA_GD_BASE\"  # ดูความคืบหน้า mirror"
