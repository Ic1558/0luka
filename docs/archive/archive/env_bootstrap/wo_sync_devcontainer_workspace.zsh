#!/usr/bin/env zsh
# wo_sync_devcontainer_workspace.zsh — one-shot: commit devcontainer files + push
# ARCHIVED: stale — hardcoded LocalProjects path, superseded by new devcontainer config.
set -euo pipefail

REPO="${HOME}/LocalProjects/02luka_local_g/g"
BRANCH="$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'UNKNOWN')"
TS="$(date +%y%m%d_%H%M%S)"
LOG="/tmp/wo_sync_devcontainer_workspace_${TS}.log"

say(){ printf "%s  %s\n" "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }
ok(){ say "✅ $*"; }
err(){ say "🛑 $*"; exit 1; }

[[ -d "$REPO" ]] || err "Repo not found: $REPO"

say "Repo: $REPO"
say "Branch: $BRANCH"
cd "$REPO"

TARGETS=(
  ".devcontainer/devcontainer.json"
  ".devcontainer/WORKSPACE_SETUP.md"
)

git status --porcelain "${TARGETS[@]}" | tee -a "$LOG" || true
git add "${TARGETS[@]}"
if git diff --cached --quiet; then
  ok "ไม่มีการเปลี่ยนแปลงใหม่ใน ${TARGETS[*]}"
else
  git commit -m "devcontainer: auto-open dual workspace + WORKSPACE_SETUP guide (${TS})"
  ok "Committed changes"
fi

git push -u origin "$BRANCH"
ok "Pushed to origin/$BRANCH"
ok "Done. Log: $LOG"
