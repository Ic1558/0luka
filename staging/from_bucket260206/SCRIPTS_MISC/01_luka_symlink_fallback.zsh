#!/usr/bin/env zsh
set -euo pipefail
[[ -d "$HOME/02luka" ]] || { echo "❌ $HOME/02luka not found"; exit 2; }
ln -snf "$HOME/02luka" "$HOME/LocalProjects/02luka_local_g"
echo "✅ Symlink set: $HOME/LocalProjects/02luka_local_g -> $HOME/02luka"
