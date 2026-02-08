#!/usr/bin/env zsh
set -euo pipefail

ACTIVE_MD="$HOME/My Drive (ittipong.c@gmail.com) (1)"
GD="$HOME/gd"
BASE="$GD/02luka"
SYNC="$GD/02luka_sync"        # shadow (ถ้ามี)
QROOT="$HOME/_gd_quarantine"  # quarantine root (ถ้ามี)
TS=$(date +%Y%m%d_%H%M%S)
LOG="$HOME/_gd_quarantine/runtime_fix_${TS}.log"
mkdir -p "${LOG:h}"

note() { print -P "%F{cyan}[wo]%f $*"; }
ok()   { print -P "%F{green}✓%f $*"; }
warn() { print -P "%F{yellow}!%f $*"; }
fail() { print -ru2 -- "[ERR] $*"; exit 2; }

# 0) ยืนยันฐาน Mirror
[[ -L "$GD" ]] || fail "~/gd missing or not a symlink"
[[ "$(readlink "$GD")" == "$ACTIVE_MD" ]] || fail "~/gd not pointing to ACTIVE My Drive"

# 1) แก้ ~/.zshrc ให้ LUKA_GD_BASE="$HOME/gd"
if [[ -f "$HOME/.zshrc" ]]; then
  # macOS sed in-place
  sed -i '' '/^[[:space:]]*export[[:space:]]\+LUKA_GD_BASE=/d' "$HOME/.zshrc"
fi
print 'export LUKA_GD_BASE="$HOME/gd"' >> "$HOME/.zshrc"
ok "Set LUKA_GD_BASE=\$HOME/gd (appended to ~/.zshrc).  Reload later: exec zsh"

# 2) กู้ไฟล์ระบบที่หาย แบบ non-destructive (เติมเฉพาะที่ขาด)
mkdir -p "$BASE"
restore_one() {
  local fname="$1" found=""
  # ค้นหาใน quarantine (ใหม่สุดก่อน) และใน sync
  if [[ -d "$QROOT" ]]; then
    found="$(find "$QROOT" -type f -name "$fname" -print0 2>/dev/null | xargs -0 ls -1t 2>/dev/null | head -n1 || true)"
  fi
  if [[ -z "$found" && -d "$SYNC" ]]; then
    found="$(find "$SYNC" -type f -name "$fname" -print0 2>/dev/null | xargs -0 ls -1t 2>/dev/null | head -n1 || true)"
  fi
  if [[ -n "$found" ]]; then
    if [[ ! -e "$BASE/$fname" ]]; then
      rsync -a --ignore-existing "$found" "$BASE/$fname"
      ok "Restored $fname from: ${found#"$HOME/"}"
    else
      ok "$fname already present — skip restore"
    fi
  else
    warn "Not found: $fname (check other backups later)"
  fi
}
restore_one "ai_read_min.v2.json"
restore_one "ai_read.manifest.json"

# 3) รีเฟรช SOT links
SOT="$HOME/02luka/google_drive"
mkdir -p "$SOT"
ln -sfn "$BASE" "$SOT/02luka"
[[ -d "$SYNC" ]] && ln -sfn "$SYNC" "$SOT/02luka_sync" || true
ok "SOT refreshed: ~/02luka/google_drive/{02luka,02luka_sync}"

# 4) รายงานยืนยัน (log เก็บไว้ด้วย)
{
  echo "=== RUNTIME VERIFY @ ${TS} ==="
  echo "-- gd symlink --"
  ls -ld "$GD"; echo "-> $(readlink "$GD")"
  echo
  echo "-- key files --"
  for f in ai_read_min.v2.json ai_read.manifest.json; do
    test -f "$BASE/$f" && echo "OK  $f" || echo "MISS $f"
  done
  echo
  echo "-- SOT --"
  ls -l "$SOT" || true
} | tee -a "$LOG"

ok "Done. Log: ${LOG#"$HOME/"}"
