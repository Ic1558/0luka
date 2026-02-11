#!/usr/bin/env zsh
set -euo pipefail
set +H

# ---------- CONFIG ----------
# Detect SOT (Google Drive) root
ROOT=""
for CAND in "$HOME"/My\ Drive*/02luka; do
  [[ -d "$CAND" ]] && ROOT="$CAND" && break
done
[[ -n "$ROOT" ]] || { print -ru2 "ERR: 02luka SOT not found under My Drive"; exit 2; }

# Where to scan (updated to match actual structure)
SCAN_DIRS=(
  "$ROOT/g"
  "$ROOT/g/reconcile"
  "$ROOT/g/shadow"
  "$ROOT/g/shadow_apply"
  "$ROOT/g/lib"
  "$ROOT/g/ops"
  "$ROOT/f/bridge"
  "$ROOT/f/ai_context"
  "$ROOT/a"
)

# File types to scan
EXTS=(sh zsh py js ts toml json yml yaml md)

# Legacy path patterns (add as needed)
LEGACY_PATTERNS=(
  '$HOME/02luka/google_drive/02luka'
  '$HOME/02luka/google_drive'
  '/Users/icmini/My Drive (ittipong.c@gmail.com) (1)/02luka/google_drive/02luka'
  '/Users/icmini/My Drive (ittipong.c@gmail.com) (1)/02luka/google_drive'
  '~/02luka/google_drive/02luka'
  '~/02luka/google_drive'
  '$HOME/02luka/g'
  '$HOME/02luka/logs'
  '/Users/icmini/My Drive (ittipong.c@gmail.com) (1)/02luka'
)

# Replacement rules (ordered)
# Map any legacy root → $ROOT (quoted for spaces)
REPL_TO="$ROOT"
# ---------- END CONFIG ----------

TS=$(date +%Y%m%d_%H%M%S)
OUTDIR="$ROOT/c/reports"
mkdir -p "$OUTDIR"
AUDIT="$OUTDIR/path_audit_$TS.csv"
FIXLOG="$OUTDIR/path_fix_$TS.log"
DRY="${DRYRUN:-1}"     # default dry-run
BACKUP_DIR="$ROOT/g/logs/path_fix_backups_$TS"
mkdir -p "$BACKUP_DIR"

print "file,line,matched_legacy,new_path" > "$AUDIT"

# Build find expression for extensions
ext_glob=$(printf -- "-name *.%s -o " "${EXTS[@]}")
ext_glob="${ext_glob% -o }"

# Collect candidates
typeset -a files
for D in "${SCAN_DIRS[@]}"; do
  [[ -d "$D" ]] || continue
  while IFS= read -r f; do files+=("$f"); done < <(eval "find \"$D\" \\( $ext_glob \\) -type f -print 2>/dev/null")
done

# Audit
for f in "${files[@]}"; do
  [[ -f "$f" ]] || continue
  nl -ba "$f" | while IFS= read -r line; do
    for pat in "${LEGACY_PATTERNS[@]}"; do
      if print -r -- "$line" | grep -Fq -- "${pat//\$/\\$}"; then
        lineno="${line%%[[:space:]]*}"
        echo "\"$f\",$lineno,\"$pat\",\"$REPL_TO\"" >> "$AUDIT"
      fi
    done
  done
done

# If only auditing, stop here
if [[ "$DRY" == "1" ]]; then
  print "\n[DRYRUN] Wrote audit: $AUDIT"
  exit 0
fi

# Apply fixes (in-place with backups)
# Use Perl for robust in-place with backup suffix
print "[APPLY] Starting fixes…" | tee -a "$FIXLOG"
for f in "${files[@]}"; do
  changed=0
  for pat in "${LEGACY_PATTERNS[@]}"; do
    # escape slashes for perl
    old="${pat//\//\\/}"
    new="${REPL_TO//\//\\/}"
    if grep -Fq -- "$pat" "$f"; then
      cp -p "$f" "$BACKUP_DIR/$(basename "$f").bak.$TS"
      /usr/bin/perl -0777 -pe "s/${old}/${new}/g" "$BACKUP_DIR/$(basename "$f").bak.$TS" > "$f"
      changed=1
    fi
  done
  (( changed )) && print "fixed: $f" >> "$FIXLOG"
done

print "[APPLY] Backups in: $BACKUP_DIR" | tee -a "$FIXLOG"
print "[APPLY] Audit  : $AUDIT" | tee -a "$FIXLOG"
print "[APPLY] Log    : $FIXLOG" | tee -a "$FIXLOG"
