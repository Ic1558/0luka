#!/usr/bin/env zsh
set -euo pipefail
ROOT="${ROOT:-$HOME/0luka}"
exec python3 "$ROOT/modules/studio/runtime/executor.py"
