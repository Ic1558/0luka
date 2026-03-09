#!/usr/bin/env zsh
# wo_runtime_realign_and_restore.zsh — one-shot: realign ~/gd, restore key JSON files, refresh SOT
# ARCHIVED: incident-specific realign from GD migration period.
set -euo pipefail

ACTIVE_MD="$HOME/My Drive (ittipong.c@gmail.com) (1)"
GD="$HOME/gd"
BASE="$GD/02luka"
SYNC="$GD/02luka_sync"
QROOT="$HOME/_gd_quarantine"
TS=$(date +%Y%m%d_%H%M%S)
LOG="$HOME/_gd_quarantine/runtime_fix_${TS}.log"
mkdir -p "${LOG:h}"

note() { print -P "%F{cyan}[wo]%f $*"; }
ok()   { print -P "%F{green}✓%f $*"; }
warn() { print -P "%F{yellow}!%f $*"; }
fail() { print -ru2 -- "[ERR] $*"; exit 2; }

[[ -L "$GD" ]] || fail "~/gd missing or not a symlink"
[[ "$(readlink "$GD")" == "$ACTIVE_MD" ]] || fail "~/gd not pointing to ACTIVE My Drive"

if [[ -f "$HOME/.zshrc" ]]; then
  sed -i '' '/^[[:space:]]*export[[:space:]]\+LUKA_GD_BASE=/d' "$HOME/.zshrc"
fi
print 'export LUKA_GD_BASE="$HOME/gd"' >> "$HOME/.zshrc"
ok "Set LUKA_GD_BASE=\$HOME/gd"

mkdir -p "$BASE"
restore_one() {
  local fname="$1" found=""
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
    warn "Not found: $fname"
  fi
}
restore_one "ai_read_min.v2.json"
restore_one "ai_read.manifest.json"

SOT="$HOME/02luka/google_drive"
mkdir -p "$SOT"
ln -sfn "$BASE" "$SOT/02luka"
[[ -d "$SYNC" ]] && ln -sfn "$SYNC" "$SOT/02luka_sync" || true
ok "SOT refreshed"

{
  echo "=== RUNTIME VERIFY @ ${TS} ==="
  ls -ld "$GD"; echo "-> $(readlink "$GD")"
  for f in ai_read_min.v2.json ai_read.manifest.json; do
    test -f "$BASE/$f" && echo "OK  $f" || echo "MISS $f"
  done
  ls -l "$SOT" || true
} | tee -a "$LOG"

ok "Done. Log: ${LOG#"$HOME/"}"
