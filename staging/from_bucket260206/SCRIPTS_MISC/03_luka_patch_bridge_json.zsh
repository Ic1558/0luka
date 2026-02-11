#!/usr/bin/env zsh
set -euo pipefail
ROOT="$HOME/02luka"
TARGETS=(
  "$ROOT/bridge/inbox/CLC"
)
APPLY="${APPLY:-0}"
FROM_RX="/Users/[^/]+/LocalProjects/02luka_local_g"
TO_PATH="$HOME/02luka"
echo "== Patch bridge JSON (APPLY=$APPLY) =="

# หาไฟล์ .json ที่มี path เก่า
LIST=()
for T in "${TARGETS[@]}"; do
  [[ -d "$T" ]] || continue
  while IFS= read -r f; do LIST+=("$f"); done < <(grep -rlE "$FROM_RX" "$T" --include='*.json' || true)
done

[[ ${#LIST[@]} -gt 0 ]] || { echo "No JSON contains old path"; exit 0; }

for f in "${LIST[@]}"; do
  echo "--- $f"
  if [[ "$APPLY" = "1" ]]; then
    # เขียนแบบ atomic
    tmp="$(mktemp)"
    perl -0777 -pe "s|$FROM_RX|$TO_PATH|g" "$f" > "$tmp"
    mv "$tmp" "$f"
    echo "  ✔ patched"
  else
    # พรีวิว
    perl -0777 -pe "s|$FROM_RX|$TO_PATH|g" "$f" | diff -u "$f" - || echo "  (no visible diff?)"
  fi
done
echo "✅ Done (APPLY=$APPLY)"
