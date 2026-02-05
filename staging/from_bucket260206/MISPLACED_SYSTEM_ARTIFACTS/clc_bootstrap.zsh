#!/usr/bin/env zsh
set -euo pipefail

# Force correct base path
LUKA_GD_BASE="$HOME/gd"
ACTIVE_MD="$HOME/My Drive (ittipong.c@gmail.com) (1)"

say()  { print -P "%F{cyan}[clc]%f $*"; }
ok()   { print -P "%F{green}✓%f $*"; }
fail() { print -ru2 -- "[ERR] $*"; exit 2; }

# 1) gd ต้องเป็น symlink
[[ -L "$LUKA_GD_BASE" ]] || fail "~/gd missing or not a symlink"

# 2) ต้องชี้ไป ACTIVE_MD แบบเท่ากันเป๊ะ
cur="$(readlink "$LUKA_GD_BASE")"
[[ "$cur" == "$ACTIVE_MD" ]] || fail "~/gd not pointing to ACTIVE My Drive ($cur != $ACTIVE_MD)"

# 3) ป้องกันเผลอใช้ Stream path เดิม
[[ "$cur" != *"/Library/CloudStorage/"* ]] || fail "gd points to old STREAM mount. Fix gd first."

ok "~/gd -> $cur"

# 4) รีเฟรช SOT links (idempotent)
SOT="$HOME/02luka/google_drive"
mkdir -p "$SOT"

link_safe() {
  local src="$1" dst="$2"
  if [[ -d "$src" ]]; then
    ln -sfn "$src" "$dst"
    ok "SOT link: ${dst##$HOME/} -> ${src##$HOME/}"
  else
    say "skip (missing): ${src##$HOME/}"
  fi
}

link_safe "$LUKA_GD_BASE/02luka"      "$SOT/02luka"
link_safe "$LUKA_GD_BASE/02luka_sync" "$SOT/02luka_sync"

print; ok "SUMMARY"
ls -ld "$LUKA_GD_BASE"
[[ -d "$SOT" ]] && ls -l "$SOT" || true
