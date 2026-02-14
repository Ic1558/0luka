#!/usr/bin/env zsh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LABEL="com.theedges.luka.email_ingest"
SRC_PLIST="$ROOT/ops/launchd/${LABEL}.plist"
DST_PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_JSONL="$ROOT/observability/logs/email_orchestrator.jsonl"

mkdir -p "$HOME/Library/LaunchAgents" "$ROOT/observability/logs"
cp "$SRC_PLIST" "$DST_PLIST"

launchctl unload "$DST_PLIST" >/dev/null 2>&1 || true
launchctl load "$DST_PLIST"

echo "Installed: $DST_PLIST"
launchctl list | rg "$LABEL" || true

echo "--- tail $LOG_JSONL ---"
tail -n 20 "$LOG_JSONL" 2>/dev/null || echo "(no log entries yet)"
