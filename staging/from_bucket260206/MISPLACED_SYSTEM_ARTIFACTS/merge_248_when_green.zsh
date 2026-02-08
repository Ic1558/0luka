#!/usr/bin/env zsh
set -euo pipefail
PR=248
REPO="Ic1558/02luka"
POLL_SECONDS=${POLL_SECONDS:-15}
MAX_WAIT=${MAX_WAIT:-900} # 15 นาที

need() { command -v "$1" >/dev/null || { echo "Missing: $1"; exit 1; }; }
need gh; need jq

echo "⏳ Watching PR #$PR until mergeable & not BLOCKED…"
elapsed=0
while (( elapsed < MAX_WAIT )); do
  json="$(gh pr view $PR --repo $REPO --json mergeable,mergeStateStatus,statusCheckRollup 2>/dev/null || true)"
  ms="$(jq -r '.mergeStateStatus // "UNKNOWN"' <<<"$json")"
  mg="$(jq -r '.mergeable // "UNKNOWN"' <<<"$json")"

  # สรุปเฉพาะ checks ที่มีสรุปแล้ว
  checks="$(jq -r '[.statusCheckRollup[]? | select(.conclusion!=null) | {c:.context, r:.conclusion}]' <<<"$json" 2>/dev/null || echo '[]')"
  echo "• mergeStateStatus=$ms mergeable=$mg checks=$(jq -r 'map("\(.c):\(.r)")|join(", ")' <<<"$checks")"

  if [[ "$mg" == "MERGEABLE" && "$ms" != "BLOCKED" ]]; then
    if [[ "${DRY_RUN:-0}" == "1" ]]; then
      echo "✅ (DRY-RUN) Would merge PR #$PR now."
      exit 0
    fi
    gh pr merge $PR --repo $REPO --squash --delete-branch \
      --subject "feat(telemetry): Phase 21.1 — unified telemetry API (minimal) (#$PR)" \
      --body "Unified event logging infrastructure. JSON Lines format with contract: ts/agent/event/ok/detail. Initial OCR integration for sha256_validation events. No CI changes. Foundation for Phase 22 dashboard."
    echo "🎉 Merged PR #$PR"
    exit 0
  fi

  sleep $POLL_SECONDS
  elapsed=$((elapsed + POLL_SECONDS))
done

echo "⚠️ Timeout waiting for PR #$PR to be mergeable."
exit 1
