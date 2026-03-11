#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
SCAN_RUNNER="$ROOT_DIR/runtime/services/antigravity_scan/runner.zsh"
REALTIME_RUNNER="$ROOT_DIR/runtime/services/antigravity_realtime/runner.zsh"

pm2 delete Antigravity-Monitor 2>/dev/null || true
pm2 delete OptionBugHunter 2>/dev/null || true

pm2 start "$SCAN_RUNNER" --name "Antigravity-Monitor"
pm2 start "$REALTIME_RUNNER" --name "OptionBugHunter"

pm2 save
pm2 list
