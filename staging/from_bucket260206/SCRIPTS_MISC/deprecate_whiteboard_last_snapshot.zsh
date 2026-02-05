#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
SRC="$ROOT/system/tools/whiteboard/whiteboard_last_snapshot.zsh"
LEG="$ROOT/system/tools/whiteboard/_legacy"
DST="$LEG/whiteboard_last_snapshot.zsh"
README="$LEG/README.md"

echo "[deprecate] ROOT=$ROOT"
echo "[deprecate] SRC=$SRC"

mkdir -p "$LEG"

if [[ ! -f "$SRC" ]]; then
  echo "[deprecate] NOTE: source file not found. Nothing to move."
else
  if [[ -f "$DST" ]]; then
    echo "[deprecate] NOTE: destination already exists: $DST"
    echo "[deprecate] Refusing to overwrite. Move manually if intended."
    exit 2
  fi
  mv "$SRC" "$DST"
  echo "[deprecate] moved -> $DST"
fi

# Deprecation notice (append-safe)
if [[ ! -f "$README" ]]; then
  cat > "$README" <<'MD'
# Legacy Whiteboard Tools

This folder contains deprecated tools kept for audit/rollback.

MD
fi

if ! grep -q "whiteboard_last_snapshot.zsh" "$README"; then
  cat >> "$README" <<'MD'
## whiteboard_last_snapshot.zsh
- **Deprecated**: 2026-02-05
- **Reason**: Obsolete pointer path (`last_snapshot_pointer.txt` vs `pointers/last_snapshot.txt`)
- **Replacement**: Use alias `last_snapshot` or read `observability/whiteboard/pointers/last_snapshot.txt` directly
- **Impact**: Zero (no active references found at time of deprecation)

MD
  echo "[deprecate] wrote README entry -> $README"
else
  echo "[deprecate] README already mentions whiteboard_last_snapshot.zsh (skip)"
fi

echo "[deprecate] VERIFY: grep for references (should be empty or legacy-only)"
# Search both system/ and tools/ to catch any drift
rg -n "whiteboard_last_snapshot\.zsh|last_snapshot_pointer\.txt" \
  "$ROOT/system" "$ROOT/tools" "$ROOT" 2>/dev/null || true

echo "[deprecate] DONE ✅"
echo "Rollback (if needed): mv '$DST' '$SRC'"
