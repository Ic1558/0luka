#!/usr/bin/env zsh
# merge_248_when_green.zsh — One-shot merging of PR #248.
# ARCHIVED: Historical PR-specific merge helper.
set -euo pipefail
PR=248
REPO="Ic1558/02luka"
POLL_SECONDS=${POLL_SECONDS:-15}
MAX_WAIT=${MAX_WAIT:-900}

need() { command -v "$1" >/dev/null || { echo "Missing: $1"; exit 1; }; }
need gh; need jq

echo "⏳ Watching PR #$PR until mergeable & not BLOCKED…"
elapsed=0
while (( elapsed < MAX_WAIT )); do
  json="$(gh pr view $PR --repo $REPO --json mergeable,mergeStateStatus,statusCheckRollup 2>/dev/null || true)"
  ms="$(jq -r '.mergeStateStatus // "UNKNOWN"' <<<"$json")"
  mg="$(jq -r '.mergeable // "UNKNOWN"' <<<"$json")"
  checks="$(jq -r '[.statusCheckRollup[]? | select(.conclusion!=null) | {c:.context, r:.conclusion}]' <<<"$json" 2>/dev/null || echo '[]')"
  echo "• mergeStateStatus=$ms mergeable=$mg checks=$(jq -r 'map("\(.c):\(.r)")|join(", ")' <<<"$checks")"

  if [[ "$mg" == "MERGEABLE" && "$ms" != "BLOCKED" ]]; then
    gh pr merge $PR --repo $REPO --squash --delete-branch \
      --subject "feat(telemetry): Phase 21.1 — unified telemetry API (minimal) (#$PR)" \
      --body "Unified logging infrastructure. Foundation for Phase 22 dashboard."
    echo "🎉 Merged PR #$PR"
    exit 0
  fi
  sleep $POLL_SECONDS
  elapsed=$((elapsed + POLL_SECONDS))
done
echo "⚠️ Timeout waiting for PR #$PR to be mergeable."
exit 1
