#!/usr/bin/env zsh
# wo_quiet_autosync_container.zsh — one-shot: add container path guard to autosync scripts
# ARCHIVED: container workspace guard patcher, one-time migration fix.
set -euo pipefail
SOT="${LUKA_HOME:-$HOME/02luka}"
STAMP=$(date +%Y%m%d_%H%M%S)
BACKUP="$HOME/02luka_BACKUP_${STAMP}_autosync"
mkdir -p "$BACKUP"

typeset -a CANDS
while IFS= read -r -d '' f; do CANDS+=("$f"); done < <(
  find "$SOT" -type f \( -name "*.zsh" -o -name "*.sh" \) -print0 | xargs -0 grep -l "/workspaces/02luka-fresh" 2>/dev/null | tr '\n' '\0'
)

for f in "${CANDS[@]:-}"; do
  rel="${f#$SOT/}"
  cp -v "$f" "$BACKUP/${rel//\//__}"
  if ! grep -q "02luka: container path guard" "$f"; then
    cat >> "$f" <<'EOF'

# 02luka: container path guard
if [[ ! -d /workspaces/02luka-fresh ]]; then
  echo "[autosync] ↷ skip container step (not found)"
  export SKIP_CONTAINER=1
fi
EOF
  fi
  echo "✓ guard added: $rel"
done

echo "Backup: $BACKUP"
