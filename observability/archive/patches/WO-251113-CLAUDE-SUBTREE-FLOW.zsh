#!/usr/bin/env zsh
set -euo pipefail

REPO="$HOME/02luka"
cd "$REPO"

log() { print -P "[$(date +%H:%M:%S)] %F{cyan}$1%f"; }
ok()  { print -P "%F{green}✓%f $1"; }
fail(){ print -P "%F{red}✗%f $1"; exit 1; }

# 0) Preconditions
[[ -x tools/mem_sync_from_core.zsh ]]   || fail "tools/mem_sync_from_core.zsh not found/executable"
[[ -x tools/mem_push_to_memory.zsh ]]   || fail "tools/mem_push_to_memory.zsh not found/executable"
command -v gh >/dev/null                 || fail "GitHub CLI (gh) is required"
git rev-parse --is-inside-work-tree >/dev/null || fail "Not a git repo: $REPO"

# 1) Pull latest from memory subtree
log "Pulling subtree from memory/main into _memory/ ..."
if tools/mem_sync_from_core.zsh; then
  ok "Subtree pull OK"
else
  fail "Subtree pull failed"
fi

# 2) Write integration ping into _memory (unique marker)
STAMP=$(date -u +%Y%m%d_%H%M%S)
DEST="_memory/GG/context"
mkdir -p "$DEST"
PING="$DEST/INTEGRATION_PING_${STAMP}.md"
cat > "$PING" <<EOF
# Integration Ping

- when: $(date -u +%FT%TZ)
- by: WO-251113-CLAUDE-SUBTREE-FLOW
- note: verifying subtree split/push + CI auto-index linkage
EOF

git add "$PING" || true
if git commit -m "chore(memory): integration ping ${STAMP} [skip ci]"; then
  ok "Committed _memory ping"
else
  log "No commit created (perhaps identical content)"
fi

# 3) Push subtree back to 02luka-memory
log "Pushing subtree to memory:main ..."
if tools/mem_push_to_memory.zsh; then
  ok "Subtree push OK"
else
  fail "Subtree push failed"
fi

# 4) Trigger CI auto-index (uses _memory subtree from main checkout)
log "Triggering Auto-Index workflow ..."
if gh workflow run auto-index.yml >/dev/null; then
  ok "Workflow dispatched"
else
  fail "Failed to dispatch auto-index"
fi

# 5) Wait for latest run to finish & summarize
log "Waiting for latest Auto-Index run to complete ..."
WF_NAME="Auto-Index Memory Repository"
RUN_ID=$(gh run list --workflow "auto-index.yml" --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null || true)
[[ -z "$RUN_ID" ]] && RUN_ID=$(gh run list --workflow "$WF_NAME" --limit 1 --json databaseId --jq '.[0].databaseId' 2>/dev/null || true)
[[ -n "$RUN_ID" ]] || fail "Cannot resolve run id"

if gh run watch "$RUN_ID" --exit-status; then
  ok "Auto-Index run $RUN_ID succeeded"
else
  fail "Auto-Index run $RUN_ID failed"
fi

log "Artifacts / key files:"
gh run view "$RUN_ID" --log --exit-status >/dev/null || true
test -f hub/index.json && { ok "hub/index.json present"; jq -r '._meta // {}' hub/index.json 2>/dev/null || true; }

print -P "\n%F{green}=== SUMMARY ===%f"
print "Subtree pull : OK"
print "Subtree push : OK"
print "Auto-Index   : OK (run $RUN_ID)"
print "Marker file  : $PING"
