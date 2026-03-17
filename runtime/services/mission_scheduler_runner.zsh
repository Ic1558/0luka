#!/bin/zsh
# AG-P10: launchd wrapper for mission_scheduler.py
# Sources ~/.env via dotenvx, then runs one scheduler tick.
set -euo pipefail

export LUKA_RUNTIME_ROOT="/Users/icmini/0luka_runtime"
export PYTHONPATH="/Users/icmini/0luka"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

exec /opt/homebrew/bin/dotenvx run --env-file /Users/icmini/.env -- \
    /opt/homebrew/bin/python3 /Users/icmini/0luka/runtime/mission_scheduler.py
