#!/usr/bin/env zsh
set -euo pipefail

TS=$(date +%Y%m%d_%H%M%S)
QUAR="$HOME/_gd_quarantine/bind_$TS"
mkdir -p "$QUAR"

note() { print -P "%F{cyan}[wo]%f $*"; }
ok()   { print -P "%F{green}✓%f $*"; }
warn() { print -P "%F{yellow}!%f $*"; }

# 1) เลือก My Drive ตัวใหม่แบบอัตโนมัติ
cands=(
  "$HOME/My Drive (ittipong.c@gmail.com) (1)"
  "$HOME/My Drive (ittipong.c@gmail.com)"
  "$HOME/My Drive"
)
TARGET=""
for p in "${cands[@]}"; do
  if [ -d "$p" ]; then TARGET="$p"; break; fi
done
if [ -z "${TARGET:-}" ]; then
  warn "ไม่พบโฟลเดอร์ My Drive ใด ๆ — ยกเลิก"; exit 2
fi
ok "เลือก My Drive: $TARGET"

# 2) จัดการ ~/gd ให้ชี้มาที่ TARGET
if [ -e "$HOME/gd" ] && [ ! -L "$HOME/gd" ]; then
  note "พบ ~/gd เป็นโฟลเดอร์จริง → ย้ายไป quarantine"
  mv "$HOME/gd" "$QUAR/gd_dir_$TS"
fi
if [ -L "$HOME/gd" ]; then
  cur="$(readlink "$HOME/gd")"
  if [ "$cur" != "$TARGET" ]; then
    note "เปลี่ยนชี้ ~/gd: $cur -> $TARGET (ของเก่าเก็บ log ไว้ใน $QUAR)"
    rm -f "$HOME/gd"
    ln -s "$TARGET" "$HOME/gd"
  else
    ok "~/gd ชี้ถูกอยู่แล้ว"
  fi
else
  note "สร้าง symlink ~/gd -> $TARGET"
  ln -s "$TARGET" "$HOME/gd"
fi

# 3) ลดความงง: quarantine symlink ~/luka (ถ้ามี)
if [ -L "$HOME/luka" ]; then
  mv "$HOME/luka" "$QUAR/luka_symlink_$TS"
  ok "ย้าย ~/luka (symlink) ไป quarantine"
fi

# 4) สร้าง SOT นอก My Drive (ไม่ recursive)
SOT="$HOME/02luka/google_drive"
mkdir -p "$SOT"

# 4.1) 02luka
if [ -d "$HOME/gd/02luka" ]; then
  ln -sfn "$HOME/gd/02luka" "$SOT/02luka"
  ok "SOT: $SOT/02luka -> ~/gd/02luka"
else
  warn "ข้ามสร้าง $SOT/02luka (ไม่พบ ~/gd/02luka)"
fi

# 4.2) 02luka_sync
if [ -d "$HOME/gd/02luka_sync" ]; then
  ln -sfn "$HOME/gd/02luka_sync" "$SOT/02luka_sync"
  ok "SOT: $SOT/02luka_sync -> ~/gd/02luka_sync"
else
  warn "ข้ามสร้าง $SOT/02luka_sync (ไม่พบ ~/gd/02luka_sync)"
fi

# 5) ใส่ env var ให้สคริปต์ใช้งานง่าย
if ! grep -q 'LUKA_GD_BASE=' "$HOME/.zshrc" 2>/dev/null; then
  print 'export LUKA_GD_BASE="$HOME/gd"' >> "$HOME/.zshrc"
  ok "เพิ่ม LUKA_GD_BASE ลงใน ~/.zshrc"
else
  ok "พบ LUKA_GD_BASE ใน ~/.zshrc แล้ว"
fi

# 6) สรุปผล
print
ok "SUMMARY"
ls -ld "$HOME/gd"
[ -d "$SOT" ] && ls -l "$SOT" || true
print "Quarantine: $QUAR"
print
ok "เสร็จสิ้น — แนะนำ: exec zsh แล้วลอง cd ~/gd/02luka"
