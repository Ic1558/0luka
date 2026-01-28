#!/usr/bin/env zsh
set -euo pipefail

ROOT="${ROOT:-${LUKA_SOT:-${HOME}/0luka}}"
HANDOFF_JSON="${ROOT}/observability/artifacts/handoff_latest.json"
LEGACY_JSON="${ROOT}/observability/reports/handoff_latest.json"
LEGACY_MD="${ROOT}/observability/reports/handoff_latest.md"

if [[ -f "${HANDOFF_JSON}" ]]; then
  echo "[handoff_latest.json]"
  python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1], "r", encoding="utf-8")), indent=2))' "${HANDOFF_JSON}"
  echo ""
else
  echo "[handoff_latest.json] missing: ${HANDOFF_JSON}" >&2
fi

if [[ -f "${LEGACY_JSON}" ]]; then
  echo "[handoff_latest.json (legacy reports/)]"
  python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1], "r", encoding="utf-8")), indent=2))' "${LEGACY_JSON}"
  echo ""
fi

if [[ -f "${LEGACY_MD}" ]]; then
  echo "[handoff_latest.md (legacy reports/)]"
  cat "${LEGACY_MD}"
fi
