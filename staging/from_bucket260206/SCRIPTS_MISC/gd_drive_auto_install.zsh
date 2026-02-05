#!/usr/bin/env zsh
set -euo pipefail
set +H
setopt interactivecomments

note(){ print -r -- "[$(date +%H:%M:%S)] $*"; }

# URL สำรองหลายตัว (เปลี่ยนได้ถ้ากูเกิลสลับลิงก์)
urls=(
  "https://dl.google.com/drive-file-stream/GoogleDrive.dmg"
  "https://dl.google.com/drive-file-stream/GoogleDrive.dmg?hl=en"
)

tmpdir="$(mktemp -d)"
dmg="$tmpdir/GoogleDrive.dmg"
vol="/Volumes/Google Drive"

# ปิดแอปก่อน
osascript -e 'tell application "Google Drive" to quit' 2>/dev/null || true
pkill -x "Google Drive" 2>/dev/null || true

# ดาวน์โหลด
ok=0
for u in $urls; do
  note "ดาวน์โหลด DMG: $u"
  if curl -fL --retry 3 --retry-delay 2 -o "$dmg" "$u"; then
    ok=1; break
  fi
done
(( ok )) || { note "✖ ดาวน์โหลดไม่สำเร็จ"; exit 1; }

# เมาต์ DMG (เปิด Finder ให้ด้วย = new window)
note "เมาต์ DMG..."
hdiutil attach "$dmg" -nobrowse -quiet || { note "✖ เมาต์ไม่สำเร็จ"; exit 1; }
open "$vol" || true

# คัดลอกแอปไป /Applications (ต้องใช้ sudo)
if [ -d "$vol/Google Drive.app" ]; then
  note "ติดตั้งลง /Applications (ต้องใส่รหัสผ่าน)..."
  sudo rm -rf "/Applications/Google Drive.app" 2>/dev/null || true
  sudo ditto "$vol/Google Drive.app" "/Applications/Google Drive.app"
else
  note "✖ ไม่พบ Google Drive.app ใน $vol"; exit 1
fi

# เลิกเมาต์
note "ถอดดิสก์ DMG..."
hdiutil detach "$vol" -quiet || true

# เปิดแอปและรอให้พร้อม
note "เปิด Google Drive..."
open -a "Google Drive" || true
sleep 3

note "✅ ติดตั้งเสร็จแล้ว — ไปที่ Preferences → My Drive → เลือก Mirror files"
note "จากนั้นต้องเห็นโฟลเดอร์: '$HOME/My Drive'"
