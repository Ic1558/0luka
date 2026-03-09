#!/usr/bin/env zsh
# gm_gd_dynamic_locator.zsh — dynamically resolve Google Drive "My Drive" path
# and export LUKA_GD_ROOT + LUKA_GD_BASE. Adds to ~/.zshrc if not present.
#
# Usage:
#   source tools/bootstrap/gm_gd_dynamic_locator.zsh    # to export into current shell
#   zsh tools/bootstrap/gm_gd_dynamic_locator.zsh       # to run once and report
set -euo pipefail

print_h(){ echo; echo "=== $1 ==="; }

# 1) Search candidate paths for "My Drive"
candidates=(
  "$HOME/My Drive"
  "$HOME/Google Drive/My Drive"
  "$HOME/Library/CloudStorage"/*/My\ Drive
)

found_root=""
for c in "${candidates[@]}"; do
  for p in ${(M)~c:#*}; do
    if [[ -d "$p" ]]; then
      found_root="$p"
      break
    fi
  done
  [[ -n "$found_root" ]] && break
done

# Fallback: Spotlight
if [[ -z "$found_root" ]] && command -v mdfind >/dev/null 2>&1; then
  guess="$(mdfind "kMDItemFSName == 'My Drive'cd && kMDItemPath == '$HOME/*'" | head -n 1)"
  [[ -n "$guess" && -d "$guess" ]] && found_root="$guess"
fi

# 2) Resolve paths
if [[ -z "$found_root" ]]; then
  echo "❌ 'My Drive' not found under $HOME"; exit 1
fi

GD_ROOT="$found_root"
GD_02LUKA="$GD_ROOT/02luka"

print_h "Resolved Google Drive Roots"
echo "GD_ROOT   : $GD_ROOT"
echo "GD_02LUKA : $GD_02LUKA"

# 3) Warn if 02luka not yet visible (may still be mirror-syncing)
if [[ ! -d "$GD_02LUKA" ]]; then
  echo "⚠️  '$GD_02LUKA' not found (may still be mirroring)"
fi

# 4) Export for current shell
export LUKA_GD_ROOT="$GD_ROOT"
export LUKA_GD_BASE="$GD_02LUKA"

# 5) Persist to ~/.zshrc (idempotent)
ensure_line() {
  local line="$1"
  grep -Fqs "$line" "$HOME/.zshrc" || echo "$line" >> "$HOME/.zshrc"
}
ensure_line ''
ensure_line '# 02luka: Google Drive dynamic paths'
ensure_line 'export LUKA_GD_ROOT="${LUKA_GD_ROOT:-$HOME/Library/CloudStorage/*/My Drive}"'
ensure_line 'export LUKA_GD_BASE="${LUKA_GD_BASE:-$LUKA_GD_ROOT/02luka}"'

print_h "Ready to use"
echo "  \$LUKA_GD_ROOT = $LUKA_GD_ROOT"
echo "  \$LUKA_GD_BASE = $LUKA_GD_BASE"
echo
echo "Check mirror: du -sh \"$LUKA_GD_BASE\""
