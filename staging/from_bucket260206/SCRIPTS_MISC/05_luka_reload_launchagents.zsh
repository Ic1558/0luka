#!/usr/bin/env zsh
set -euo pipefail
LA_DIR="$HOME/Library/LaunchAgents"
# หาไฟล์ที่อ้างอิง $HOME/02luka เพื่อ reload อย่างปลอดภัย (เฉพาะของเรา)
CAND=()
while IFS= read -r f; do CAND+=("$f"); done < <(grep -rl "$HOME/02luka" "$LA_DIR" || true)
LABELS=()
for f in "${CAND[@]}"; do
  L="$(/usr/libexec/PlistBuddy -c 'Print :Label' "$f" 2>/dev/null || true)"
  [[ -n "$L" ]] && LABELS+=("$L")
done
LABELS=("${LABELS[@]:-}")
[[ ${#LABELS[@]} -gt 0 ]] || { echo "No target labels"; exit 0; }

echo "== Reload (unload+load) these labels =="
printf '%s\n' "${LABELS[@]}"

for L in "${LABELS[@]}"; do
  launchctl unload -w "$HOME/Library/LaunchAgents/${L}.plist" 2>/dev/null || true
  launchctl load -w   "$HOME/Library/LaunchAgents/${L}.plist"
  # kickstart ถ้ารองรับ
  launchctl kickstart gui/"$(id -u)"/"$L" 2>/dev/null || true
  echo "  ✔ $L reloaded"
done
echo "✅ Done"
