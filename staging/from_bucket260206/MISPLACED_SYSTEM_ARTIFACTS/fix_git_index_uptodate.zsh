#!/usr/bin/env zsh
set -euo pipefail
cd "$HOME/02luka"

# 0) abort ops ค้าง
git merge --abort >/dev/null 2>&1 || true
git rebase --abort >/dev/null 2>&1 || true
git cherry-pick --abort >/dev/null 2>&1 || true

# 1) ถ้ามี git lock ค้าง ลบทิ้ง
rm -f .git/index.lock .git/HEAD.lock .git/shallow.lock 2>/dev/null || true

# 2) เผื่อไฟล์ติด immutable flag (macOS) ปลดก่อน
chflags -R nouchg g/apps/dashboard/data/followup.json 2>/dev/null || true

# 3) ลบไฟล์ตัวปัญหาออกจาก working tree (เราจะดึงกลับจาก origin/main)
rm -f g/apps/dashboard/data/followup.json 2>/dev/null || true

# 4) รีบิวด์ index (แก้ not uptodate แบบชัวร์)
mv .git/index "/tmp/index.bak.$(date +%s)" 2>/dev/null || true

# 5) fetch แล้ว reset ให้ตรง origin/main
git fetch origin
git reset --hard origin/main
git clean -fd

echo "OK: now at origin/main"
git status --porcelain
