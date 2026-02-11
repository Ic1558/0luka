#!/usr/bin/env zsh
set -euo pipefail
APPLY="${APPLY:-0}"
FROM_RX="/Users/[^/]+/LocalProjects/02luka_local_g"
TO_PATH="$HOME/02luka"
LA_DIR="$HOME/Library/LaunchAgents"

echo "== Scan LaunchAgents with old path (APPLY=$APPLY) =="
LIST=()
while IFS= read -r f; do LIST+=("$f"); done < <(grep -rlE "$FROM_RX" "$LA_DIR" || true)
[[ ${#LIST[@]} -gt 0 ]] || { echo "No LaunchAgents contain old path"; exit 0; }

for f in "${LIST[@]}"; do
  echo "--- $f"
  if [[ "$APPLY" = "1" ]]; then
    tmp="$(mktemp)"
    perl -0777 -pe "s|$FROM_RX|$TO_PATH|g" "$f" > "$tmp"
    plutil -lint "$tmp" >/dev/null || { echo "❌ plist invalid after patch: $f"; rm -f "$tmp"; continue; }
    mv "$tmp" "$f"
    echo "  ✔ patched"
  else
    perl -0777 -pe "s|$FROM_RX|$TO_PATH|g" "$f" | diff -u "$f" - || true
  fi
done

echo "== Suggested labels to reload =="
grep -H "<key>Label</key>" "${LIST[@]}" 2>/dev/null | sed -n 's/.*<string>\(.*\)<\/string>.*/\1/p' | sort -u || true
echo "✅ Done (APPLY=$APPLY)"
