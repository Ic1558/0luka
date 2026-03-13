#!/usr/bin/env zsh
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONPATH="/Users/icmini/0luka/repos/option"

REPO="/Users/icmini/0luka/repos/option"
VENV="$REPO/venv/bin/python3"
DOTENVX="/opt/homebrew/bin/dotenvx"
LOGDIR="$REPO/artifacts"

cd "$REPO"

mkdir -p "$LOGDIR"

if [[ ! -x "$VENV" ]]; then
  echo "controltower wrapper: python venv not found at $VENV" >&2
  exit 1
fi

if [[ ! -x "$DOTENVX" ]]; then
  echo "controltower wrapper: dotenvx not found at $DOTENVX" >&2
  exit 1
fi

exec "$DOTENVX" run -- "$VENV" modules/antigravity/realtime/control_tower.py
