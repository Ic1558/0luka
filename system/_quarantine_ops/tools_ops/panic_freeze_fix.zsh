#!/usr/bin/env zsh
# panic_freeze_fix.zsh — emergency break-glass: bootout all 02luka LaunchAgents,
#                        quarantine plists, truncate logs, kill stray processes.
# Usage: zsh panic_freeze_fix.zsh
# WARNING: stops all 02luka agents. Requires manual re-bootstrap after.
set -euo pipefail
uid=$(id -u)

echo "→ Booting out all 02luka LaunchAgents…"
for p in ~/Library/LaunchAgents/com.02luka*.plist; do
  [[ -f "$p" ]] || continue
  launchctl bootout "gui/$uid" "$p" 2>/dev/null || true
done

echo "→ Quarantining plists…"
mkdir -p ~/02luka_quarantine/LaunchAgents
mv -f ~/Library/LaunchAgents/com.02luka*.plist ~/02luka_quarantine/LaunchAgents/ 2>/dev/null || true

echo "→ Truncating noisy logs…"
SOT_DEFAULT="$HOME/02luka"
SOT_GDRIVE="$HOME/My Drive (ittipong.c@gmail.com) (1)/02luka"
for base in "$SOT_DEFAULT" "$SOT_GDRIVE"; do
  [[ -d "$base" ]] || continue
  find "$base" -maxdepth 4 -type f -name "*.log" -print0 2>/dev/null | xargs -0 -I{} sh -c ': > "$1"' sh {}
done

echo "→ Killing stray Flask/diag…"
pkill -f 'luka_diag|flask|app.py' 2>/dev/null || true

echo "✅ Done. Recommend: logout/login or reboot."
echo "   Plists quarantined at: ~/02luka_quarantine/LaunchAgents/"
echo "   Re-bootstrap via: zsh system/tools/ops/gg_autofix_after_reboot.zsh"
