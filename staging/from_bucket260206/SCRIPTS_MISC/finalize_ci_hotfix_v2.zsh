#!/usr/bin/env zsh
set -euo pipefail

BRANCH="ci/hotfix-251030-0424-v2"
LOGDIR="$HOME/02luka/logs/ci"
SRC_AUDIT="/tmp/ci_hotfix_v2_success.txt"
DEST_AUDIT="$LOGDIR/251030_ci_hotfix_v2_success.txt"
PR_TEXT="/tmp/pr_hotfix_v2_details.txt"
MONITOR="/tmp/pr_hotfix_v2_monitor.sh"

echo "== Finalizing CI Hotfix V2 =="
mkdir -p "$LOGDIR"

# 1) Preserve audit artifact
if [[ -f "$SRC_AUDIT" ]]; then
  cp -f "$SRC_AUDIT" "$DEST_AUDIT"
  echo "✅ Copied audit -> $DEST_AUDIT"
else
  echo "⚠️  Audit file not found: $SRC_AUDIT"
fi

# 2) Put PR body into clipboard (and preview)
if [[ -f "$PR_TEXT" ]]; then
  echo "----- PR Details (preview top 40 lines) -----"
  head -n 40 "$PR_TEXT" || true
  echo "---------------------------------------------"
  if command -v pbcopy >/dev/null 2>&1; then
    cat "$PR_TEXT" | pbcopy
    echo "✅ PR details copied to clipboard. Paste into the PR page and submit."
  else
    echo "⚠️ pbcopy not found. Open and copy manually: $PR_TEXT"
  fi
else
  echo "⚠️  PR details file not found: $PR_TEXT"
fi

# 3) Offer CI monitor
if [[ -f "$MONITOR" ]]; then
  read -q "REPLY?Start CI monitor now? [y/N] "; echo
  if [[ "$REPLY" == [yY] ]]; then
    LOGFILE="$LOGDIR/monitor_$(date +%Y%m%d_%H%M%S).log"
    nohup bash "$MONITOR" >"$LOGFILE" 2>&1 &
    echo "✅ CI monitor started in background. Logs: $LOGFILE"
  else
    echo "⏭️  Skipped CI monitor."
  fi
else
  echo "ℹ️  CI monitor script not found: $MONITOR"
fi

echo
echo "➡️  Now paste the PR text into the already-open PR tab and submit."
read "ok?Press Enter AFTER the PR is merged to delete the hotfix branch (or Ctrl-C to abort)..."

# 4) Delete remote branch (best-effort)
if git rev-parse --git-dir >/dev/null 2>&1; then
  echo "Deleting remote branch: $BRANCH"
  (git push origin --delete "$BRANCH" && echo "✅ Remote branch deleted.") || echo "⚠️ Unable to delete branch automatically. You can run: git push origin --delete $BRANCH"
else
  echo "⚠️ Not in a git repo. Run this inside the repo to delete the branch:"
  echo "    git push origin --delete $BRANCH"
fi

echo "🎉 Done."
