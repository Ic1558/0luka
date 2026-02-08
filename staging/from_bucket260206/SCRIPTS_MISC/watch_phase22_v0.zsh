#!/usr/bin/env zsh
set -euo pipefail
REPO="Ic1558/02luka"
while :; do
  gh pr list -R "$REPO" --search 'Phase 22' --json number,title,state | jq -e '.[] | select(.title | contains("22")) | select(.state=="OPEN")' >/dev/null 2>&1 && {
    echo "✅ Found Phase 22 v0 PR"
    gh pr list -R "$REPO" --search 'Phase 22' --json number,title,state
    exit 0
  }
  sleep 15
done
