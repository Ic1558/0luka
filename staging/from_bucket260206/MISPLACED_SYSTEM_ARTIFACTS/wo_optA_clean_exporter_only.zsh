#!/usr/bin/env zsh
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

AUTO_COMMIT="af771121"
EXPORTER_PATH="tools/telemetry/lac_metrics_exporter.py"

echo "== Fetch origin =="
git fetch origin

echo "== Verify exporter exists in autosave commit =="
git cat-file -e "${AUTO_COMMIT}:${EXPORTER_PATH}"

TMP="$(mktemp -t lac_metrics_exporter.XXXXXX.py)"
git show "${AUTO_COMMIT}:${EXPORTER_PATH}" > "${TMP}"
echo "Saved exporter to: ${TMP}"

echo "== Hard reset main to origin/main (discard local ahead/behind) =="
git checkout main
git reset --hard origin/main

echo "== Create feature branch =="
TS="$(date +%y%m%d-%H%M%S)"
BR="feat/lac-metrics-exporter-${TS}"
git checkout -b "${BR}"

echo "== Restore exporter only =="
mkdir -p "$(dirname "${EXPORTER_PATH}")"
cp -f "${TMP}" "${EXPORTER_PATH}"
rm -f "${TMP}"

echo "== Stage + commit exporter only =="
git add "${EXPORTER_PATH}"

if git diff --cached --quiet; then
  echo "Nothing staged; exporter may already exist on origin/main. Exiting."
  git status --short --branch
  exit 0
fi

git commit -m "feat(telemetry): add LAC metrics summary exporter (md+json)"

echo "== Push branch =="
git push -u origin "${BR}"

echo "== Open PR =="
gh pr create --base main --head "${BR}" \
  --title "feat(telemetry): add LAC metrics summary exporter (md+json)" \
  --body "Adds tools/telemetry/lac_metrics_exporter.py (exports LAC metrics summary to md+json). Keeps workspace artifacts out of git."

echo ""
git status --short --branch
