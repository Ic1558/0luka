#!/usr/bin/env zsh
set -euo pipefail
ROOT="$HOME/02luka"
APPLY="${APPLY:-1}"
FROM1_RX="/Users/[^/]+/LocalProjects/02luka_local_g"
FROM2="~/LocalProjects/02luka_local_g"
TO="$HOME/02luka"

patch_one() {
  local f="$1"
  local tmp; tmp="$(mktemp)"
  perl -0777 -pe "s|$FROM1_RX|$TO|g; s|\Q$FROM2\E|$TO|g" "$f" > "$tmp"
  mv "$tmp" "$f"
  echo "  ✔ $f"
}

# targets ที่มีผล runtime จริง ๆ
set +e
LIST=()
while IFS= read -r f; do LIST+=("$f"); done < <(grep -rlE "$FROM1_RX|$FROM2" "$ROOT/wo/staging" "$ROOT/logs/wo_drop_history" 2>/dev/null || true)
set -e

[[ ${#LIST[@]} -gt 0 ]] || { echo "No runtime WO/history refs"; exit 0; }

for f in "${LIST[@]}"; do patch_one "$f"; done
echo "✅ Done runtime WO/history patch"
