#!/usr/bin/env zsh
set -euo pipefail
ROOT="${ROOT:-$HOME/0luka}"
export ROOT
python3 "$ROOT/system/tools/tk/tk_guard.py"
