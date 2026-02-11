#!/usr/bin/env zsh
set -euo pipefail

# 1) สร้าง ~/gd ให้ชี้ไปยัง Stream mount
target="$HOME/Library/CloudStorage/GoogleDrive-ittipong.c@gmail.com/My Drive"
[ -e "$HOME/gd" ] && rm -rf "$HOME/gd"
ln -s "$target" "$HOME/gd"

# 2) เคลียร์โฟลเดอร์หลงเหลือ แล้วตั้ง SOT links ให้ถูก
SOT="$HOME/02luka/google_drive"
mkdir -p "$SOT"
rm -rf "$SOT/02luka_cloud"              # ลบตัวที่ไม่ควรมี
rm -f  "$SOT/02luka" "$SOT/02luka_sync" # เคลียร์ลิงก์เก่า
ln -sfn "$HOME/gd/02luka"      "$SOT/02luka"
ln -sfn "$HOME/gd/02luka_sync" "$SOT/02luka_sync"

# 3) แสดงผลตรวจสอบ
echo "=== ~/gd ===";  ls -ld "$HOME/gd"
echo "=== SOT  ===";  ls -l "$SOT"
