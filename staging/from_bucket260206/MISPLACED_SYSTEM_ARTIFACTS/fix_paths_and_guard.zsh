#!/usr/bin/env zsh
set -euo pipefail

# ====== CONSTS ======
SOT="$HOME/02luka"                       # Single Source of Truth
STAMP="manual_fix_run" # Using fixed name due to tool constraints
BACKUP="$SOT/_import_conflicts/$STAMP"
LOG="$SOT/reports/fix_paths_$STAMP.log"
mkdir -p "$BACKUP" "$SOT/reports"

log(){ print -r -- "[FIX_RUN] $*" | tee -a "$LOG"; }

log "== 02luka :: Path Cleanup & Guard =="
log "SOT = $SOT"
[[ -d "$SOT" ]] || { echo "SOT not found"; exit 1; }

# ====== 1) Normalize legacy_parent nests under SOT ======
for N in \
  "$SOT/g/legacy_parent/legacy_parent" \
  "$SOT/legacy_parent/legacy_parent"
do
  if [[ -d "$N" ]]; then
    log "Dedup nesting: $N -> ${N:h}"
    rsync -a --remove-source-files "$N"/ "$N:h"/ || true
    find "$N" -type d -empty -delete || true
  fi
done

# ====== 2) Corrals stray top-level replicas into SOT ======
for CAND in \
  "$HOME/legacy_parent" \
  "$HOME/reports" \
  "$HOME/CLC" \
  "$HOME/_import_logs" \
  "$HOME/_import_stage" \
  "$HOME/_import_conflicts"
do
  if [[ -e "$CAND" && "$CAND" != "$SOT"* ]]; then
    log "Quarantine stray: $CAND -> $BACKUP/"
    rsync -a "$CAND" "$BACKUP/" && rm -rf "$CAND"
  fi
done

# ====== 3) Ensure Google Drive symlinks point to the right places ======
GD_BASE="${LUKA_GD_BASE:-$HOME/gd}"
mkdir -p "$SOT/google_drive"
ln -snf "$GD_BASE/02luka"      "$SOT/google_drive/02luka"
ln -snf "$GD_BASE/02luka_sync" "$SOT/google_drive/02luka_sync"
log "Symlinks set: google_drive -> $GD_BASE"

# ====== 4) Declare ~/.luka_home for all helpers (single truth) ======
print -r -- "$SOT" > "$HOME/.luka_home"
log "Wrote ~/.luka_home = $SOT"

# ====== 5) Scan for hard-coded bad paths and list them ======
BADLIST="$SOT/reports/hardcoded_paths_$STAMP.txt"
rg -n --hidden --glob '!node_modules' "/Users/icmini/(?!02luka)" "$SOT" \
  | tee "$BADLIST" || true
log "Hard-coded path report -> $BADLIST"

# ====== 6) Light plist sanity check (WorkingDirectory / ProgramArguments) ======
PLLOG="$SOT/reports/launchd_paths_$STAMP.txt"
for P in $HOME/Library/LaunchAgents/com.02luka.*.plist; do
  [[ -f "$P" ]] || continue
  /usr/libexec/PlistBuddy -c 'Print :WorkingDirectory' "$P" 2>/dev/null \
    | awk -v p="$P" '{printf("[WD]%s -> %s\n", p, $0)}' | tee -a "$PLLOG" || true
  /usr/libexec/PlistBuddy -c 'Print :ProgramArguments' "$P" 2>/dev/null \
    | awk -v p="$P" '{printf("[PA]%s -> %s\n", p, $0)}' | tee -a "$PLLOG" || true
done
log "LaunchAgents path report -> $PLLOG"

log "== DONE. See log: $LOG"
