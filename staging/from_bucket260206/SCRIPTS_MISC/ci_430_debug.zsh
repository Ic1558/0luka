#!/usr/bin/env zsh
set -euo pipefail

REPO="Ic1558/02luka"
PR="430"

echo "=== PR Info ==="
gh pr view "$PR" --repo "$REPO" --json number,title,headRefName,baseRefName,url,commits,files --jq '
"PR #\(.number) \(.title)\nURL: \(.url)\nBASE: \(.baseRefName)\nHEAD: \(.headRefName)\nCommits: \(.commits.totalCount)\nFiles: \(.files.totalCount)\n"
'

echo "=== Latest PR Checks (raw) ==="
gh pr checks "$PR" --repo "$REPO" || true

echo ""
echo "=== Find latest check runs for this PR ==="
HEAD="$(gh pr view "$PR" --repo "$REPO" --json headRefName --jq .headRefName)"
echo "HEAD branch: $HEAD"

gh run list --repo "$REPO" --branch "$HEAD" -L 15

echo ""
echo "=== Dump failing jobs logs (last run for this branch) ==="
RUN_ID="$(gh run list --repo "$REPO" --branch "$HEAD" -L 1 --json databaseId --jq '.[0].databaseId')"
echo "Latest RUN_ID: $RUN_ID"
echo ""

gh run view "$RUN_ID" --repo "$REPO" --log-failed || true

echo ""
echo "=== Also show job list (names + status) ==="
gh run view "$RUN_ID" --repo "$REPO" --json jobs --jq '.jobs[] | "\(.name)\t\(.conclusion)\t\(.startedAt)"'

echo ""
echo "=== Done ==="
