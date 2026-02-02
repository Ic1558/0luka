#!/usr/bin/env zsh
set -euo pipefail
ROOT="${ROOT:-$HOME/0luka}"
exec "$ROOT/modules/studio/connector/studio.zsh" "$@"
