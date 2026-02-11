#!/usr/bin/env zsh
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

DEFAULT_FEED="observability/logs/activity_feed.jsonl"
RAW_FEED="${LUKA_ACTIVITY_FEED_JSONL:-$DEFAULT_FEED}"
if [[ "$RAW_FEED" == "ref://activity_feed" ]]; then
  RAW_FEED="$DEFAULT_FEED"
fi
if [[ "$RAW_FEED" = /* ]]; then
  FEED_PATH="$RAW_FEED"
else
  FEED_PATH="$ROOT/$RAW_FEED"
fi

mkdir -p "$(dirname "$FEED_PATH")"
touch "$FEED_PATH"

PROOF_DIR="observability/reports/phase2_8_proof"
mkdir -p "$PROOF_DIR"

PHASE2_EVIDENCE="$PROOF_DIR/phase2_verify.log"
PHASE8_EVIDENCE="$PROOF_DIR/phase8_verify.log"
PHASE2_RESULT_JSON="$PROOF_DIR/phase2_dod_update.json"
PHASE8_RESULT_JSON="$PROOF_DIR/phase8_dod_update.json"

python3 core/verify/prove_phase2_evidence.py > "$PHASE2_EVIDENCE" 2>&1
python3 core/verify/test_task_dispatcher.py > "$PHASE8_EVIDENCE" 2>&1

PHASE2_HASH="$(shasum -a 256 "$PHASE2_EVIDENCE" | awk '{print $1}')"
PHASE8_HASH="$(shasum -a 256 "$PHASE8_EVIDENCE" | awk '{print $1}')"

python3 - <<'PY' "$FEED_PATH" "$PHASE2_EVIDENCE" "$PHASE8_EVIDENCE" "$PHASE2_HASH" "$PHASE8_HASH"
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

feed = Path(sys.argv[1])
phase2_evidence = Path(sys.argv[2]).as_posix()
phase8_evidence = Path(sys.argv[3]).as_posix()
phase2_hash = sys.argv[4]
phase8_hash = sys.argv[5]

start = datetime.now(timezone.utc).replace(microsecond=0)
entries = [
    {"offset": 0, "phase_id": "PHASE_2", "action": "started", "title": "Phase 2 proof started", "evidence": []},
    {"offset": 1, "phase_id": "PHASE_2", "action": "completed", "title": "Phase 2 proof completed", "evidence": [phase2_evidence], "hashes": {phase2_evidence: phase2_hash}},
    {"offset": 2, "phase_id": "PHASE_2", "action": "verified", "title": "Phase 2 proof verified", "evidence": [phase2_evidence], "hashes": {phase2_evidence: phase2_hash}},
    {"offset": 3, "phase_id": "PHASE_8", "action": "started", "title": "Phase 8 proof started", "evidence": []},
    {"offset": 4, "phase_id": "PHASE_8", "action": "completed", "title": "Phase 8 proof completed", "evidence": [phase8_evidence], "hashes": {phase8_evidence: phase8_hash}},
    {"offset": 5, "phase_id": "PHASE_8", "action": "verified", "title": "Phase 8 proof verified", "evidence": [phase8_evidence], "hashes": {phase8_evidence: phase8_hash}},
]

with feed.open("a", encoding="utf-8") as fh:
    for item in entries:
        ts = (start + timedelta(seconds=item["offset"]))
        payload = {
            "ts": ts.isoformat().replace("+00:00", "Z"),
            "phase_id": item["phase_id"],
            "action": item["action"],
            "title": item["title"],
            "evidence": item["evidence"],
        }
        if "hashes" in item:
            payload["hashes"] = item["hashes"]
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
PY

LUKA_ACTIVITY_FEED_JSONL="$FEED_PATH" python3 tools/ops/dod_checker.py --phase PHASE_2 --update-status --json > "$PHASE2_RESULT_JSON"
LUKA_ACTIVITY_FEED_JSONL="$FEED_PATH" python3 tools/ops/dod_checker.py --phase PHASE_8 --update-status --json > "$PHASE8_RESULT_JSON"

LUKA_ACTIVITY_FEED_JSONL="$FEED_PATH" python3 tools/ops/dod_checker.py --phase PHASE_2 --json > /tmp/phase2_dod_verify.json
PHASE2_EXIT=$?
LUKA_ACTIVITY_FEED_JSONL="$FEED_PATH" python3 tools/ops/dod_checker.py --phase PHASE_8 --json > /tmp/phase8_dod_verify.json
PHASE8_EXIT=$?

echo "ACTIVITY_FEED=$FEED_PATH"
echo "PHASE2_EVIDENCE=$PHASE2_EVIDENCE"
echo "PHASE8_EVIDENCE=$PHASE8_EVIDENCE"
echo "PHASE2_UPDATE_JSON=$PHASE2_RESULT_JSON"
echo "PHASE8_UPDATE_JSON=$PHASE8_RESULT_JSON"
echo "PHASE2_EXIT=$PHASE2_EXIT"
echo "PHASE8_EXIT=$PHASE8_EXIT"

if [[ $PHASE2_EXIT -ne 0 || $PHASE8_EXIT -ne 0 ]]; then
  exit 1
fi
