#!/usr/bin/env zsh
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${ROOT}" ]]; then
  echo "ERROR: not inside a git repo. cd into ~/02luka then rerun." >&2
  exit 1
fi
cd "$ROOT"

TOOL_DIR="tools/telemetry"
OUT_DIR="g/telemetry"

# sanity
if [[ -L "$OUT_DIR" ]]; then
  echo "OK: $OUT_DIR is a symlink (expected). Will NOT git-add outputs under it."
else
  echo "WARN: $OUT_DIR is not a symlink on this machine; still safe to proceed." >&2
fi

# ensure exporter exists (from your previous run)
if [[ ! -f "${TOOL_DIR}/lac_metrics_exporter.py" ]]; then
  echo "ERROR: missing ${TOOL_DIR}/lac_metrics_exporter.py (exporter not created?)" >&2
  exit 1
fi

# show the files that were generated (they exist already)
echo "Generated artifacts (not committing):"
ls -la "${OUT_DIR}/lac_metrics_summary_latest.json" "${OUT_DIR}/lac_metrics_summary_latest.md" 2>/dev/null || true
echo ""

# commit ONLY the tool (avoid symlinked outputs)
git add "${TOOL_DIR}/lac_metrics_exporter.py"

if git diff --cached --quiet; then
  echo "Nothing staged; exporter may already be committed. Showing last commit:"
  git show --stat -1
else
  git commit -m "feat(telemetry): add LAC metrics summary exporter (md+json)"
fi

echo ""
git status --short --branch
