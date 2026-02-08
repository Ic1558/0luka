#!/usr/bin/env zsh
set -euo pipefail
LA_DIR="$HOME/Library/LaunchAgents"
APPLY="${APPLY:-1}"   # เปิด apply เป็นค่าเริ่มต้น (เฉพาะ tilde case)
FROM='~/LocalProjects/02luka_local_g'
TO="$HOME/02luka"

LIST=()
while IFS= read -r f; do LIST+=("$f"); done < <(grep -rl "$FROM" "$LA_DIR" || true)
[[ ${#LIST[@]} -gt 0 ]] || { echo "No tilde LaunchAgents"; exit 0; }

for f in "${LIST[@]}"; do
  echo "--- $f"
  tmp="$(mktemp)"
  perl -0777 -pe "s|\Q$FROM\E|$TO|g" "$f" > "$tmp"
  plutil -lint "$tmp" >/dev/null || { echo "❌ plist invalid after patch: $f"; rm -f "$tmp"; continue; }
  mv "$tmp" "$f"
  echo "  ✔ patched"
done

echo "== reload labels =="
for f in "${LIST[@]}"; do
  L="$(/usr/libexec/PlistBuddy -c 'Print :Label' "$f" 2>/dev/null || true)"
  [[ -z "$L" ]] && continue
  launchctl unload -w "$f" 2>/dev/null || true
  launchctl load   -w "$f"
  launchctl kickstart gui/"$(id -u)"/"$L" 2>/dev/null || true
  echo "  ✔ $L reloaded"
done
echo "✅ Done"
