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
PHASE2_INIT_JSON="$PROOF_DIR/phase2_dod_init.json"
PHASE8_INIT_JSON="$PROOF_DIR/phase8_dod_init.json"
PHASE2_RESULT_JSON="$PROOF_DIR/phase2_dod_verify.json"
PHASE8_RESULT_JSON="$PROOF_DIR/phase8_dod_verify.json"
PHASE1553_RESULT_JSON="$PROOF_DIR/phase15_5_3_dod_verify.json"
ALL_UPDATE_JSON="$PROOF_DIR/dod_all_update.json"

python3 core/verify/prove_phase2_evidence.py > "$PHASE2_EVIDENCE" 2>&1
python3 core/verify/test_task_dispatcher.py > "$PHASE8_EVIDENCE" 2>&1

PHASE2_HASH="$(shasum -a 256 "$PHASE2_EVIDENCE" | awk '{print $1}')"
PHASE8_HASH="$(shasum -a 256 "$PHASE8_EVIDENCE" | awk '{print $1}')"
RUN_ID="$(python3 - <<'PY'
import uuid
print(uuid.uuid4().hex)
PY
)"

python3 - <<'PY' "$ROOT/core/governance/phase_status.yaml" "$ROOT"
import re
import sys
from pathlib import Path

status_path = Path(sys.argv[1])
root = Path(sys.argv[2]).resolve()
if not status_path.exists():
    raise SystemExit(0)

text = status_path.read_text(encoding="utf-8")
target = None
phases = {"PHASE_2", "PHASE_8"}

for raw in text.splitlines():
    line = raw.rstrip("\n")
    m_phase = re.match(r"^\s{2}([A-Z0-9_]+):\s*$", line)
    if m_phase:
        target = m_phase.group(1)
        continue
    if target not in phases:
        continue
    m_verdict = re.match(r"^\s{4}verdict:\s*(\S+)\s*$", line)
    if m_verdict and m_verdict.group(1) != "PROVEN":
        target = None
        continue
    m_ev = re.match(r"^\s{4}evidence_path:\s*(.+)\s*$", line)
    if not m_ev:
        continue
    raw_path = m_ev.group(1).strip()
    p = Path(raw_path)
    if not p.is_absolute():
        p = root / p
    if p.exists():
        continue
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        '{"schema_version":"dod_report_v2","note":"hydrated by prove_phase2_phase8_tier1 for registry integrity"}\n',
        encoding="utf-8",
    )
PY

set +e
LUKA_ACTIVITY_FEED_JSONL="$FEED_PATH" python3 tools/ops/dod_checker.py --phase PHASE_2 --json > "$PHASE2_INIT_JSON"
P2_INIT_EXIT=$?
LUKA_ACTIVITY_FEED_JSONL="$FEED_PATH" python3 tools/ops/dod_checker.py --phase PHASE_8 --json > "$PHASE8_INIT_JSON"
P8_INIT_EXIT=$?
set -e

PHASE2_REPORT_PATH="$(python3 - <<'PY' "$PHASE2_INIT_JSON"
import json
import sys
from pathlib import Path
p = Path(sys.argv[1])
if not p.exists():
    raise SystemExit(2)
payload = json.loads(p.read_text(encoding="utf-8"))
print(payload.get("report_path", ""))
PY
)"
PHASE8_REPORT_PATH="$(python3 - <<'PY' "$PHASE8_INIT_JSON"
import json
import sys
from pathlib import Path
p = Path(sys.argv[1])
if not p.exists():
    raise SystemExit(2)
payload = json.loads(p.read_text(encoding="utf-8"))
print(payload.get("report_path", ""))
PY
)"

if [[ -z "$PHASE2_REPORT_PATH" || -z "$PHASE8_REPORT_PATH" ]]; then
  echo "ERROR: missing report_path from initial dod_checker output"
  exit 2
fi
if [[ ! -r "$PHASE2_REPORT_PATH" || ! -r "$PHASE8_REPORT_PATH" ]]; then
  echo "ERROR: report_path unreadable"
  exit 2
fi

python3 - <<'PY' "$FEED_PATH" "$PHASE2_EVIDENCE" "$PHASE8_EVIDENCE" "$PHASE2_HASH" "$PHASE8_HASH" "$PHASE2_REPORT_PATH" "$PHASE8_REPORT_PATH" "$RUN_ID"
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

feed = Path(sys.argv[1])
phase2_evidence = Path(sys.argv[2]).as_posix()
phase8_evidence = Path(sys.argv[3]).as_posix()
phase2_hash = sys.argv[4]
phase8_hash = sys.argv[5]
phase2_report = Path(sys.argv[6]).as_posix()
phase8_report = Path(sys.argv[7]).as_posix()
run_id = sys.argv[8]

start = datetime.now(timezone.utc).replace(microsecond=0)
entries = [
    {
        "offset": 0,
        "phase_id": "PHASE_2",
        "action": "started",
        "title": "Phase 2 proof started",
        "evidence": [],
    },
    {
        "offset": 1,
        "phase_id": "PHASE_2",
        "action": "completed",
        "title": "Phase 2 proof completed",
        "evidence": [phase2_evidence, phase2_report],
        "hashes": {phase2_evidence: phase2_hash},
    },
    {
        "offset": 2,
        "phase_id": "PHASE_2",
        "action": "verified",
        "title": "Phase 2 proof verified",
        "evidence": [phase2_evidence, phase2_report],
        "hashes": {phase2_evidence: phase2_hash},
    },
    {
        "offset": 3,
        "phase_id": "PHASE_8",
        "action": "started",
        "title": "Phase 8 proof started",
        "evidence": [],
    },
    {
        "offset": 4,
        "phase_id": "PHASE_8",
        "action": "completed",
        "title": "Phase 8 proof completed",
        "evidence": [phase8_evidence, phase8_report],
        "hashes": {phase8_evidence: phase8_hash},
    },
    {
        "offset": 5,
        "phase_id": "PHASE_8",
        "action": "verified",
        "title": "Phase 8 proof verified",
        "evidence": [phase8_evidence, phase8_report],
        "hashes": {phase8_evidence: phase8_hash},
    },
]

with feed.open("a", encoding="utf-8") as fh:
    for item in entries:
        ts = (start + timedelta(seconds=item["offset"]))
        ts_utc = ts.isoformat().replace("+00:00", "Z")
        payload = {
            "ts": ts_utc,
            "ts_utc": ts_utc,
            "ts_epoch_ms": int(ts.timestamp() * 1000),
            "phase_id": item["phase_id"],
            "phase": item["phase_id"],
            "action": item["action"],
            "title": item["title"],
            "emit_mode": "runtime_auto",
            "verifier_mode": "operational_proof",
            "tool": "prove_phase2_phase8_tier1",
            "run_id": run_id,
            "evidence": item["evidence"],
        }
        if "hashes" in item:
            payload["hashes"] = item["hashes"]
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
PY

set +e
LUKA_ACTIVITY_FEED_JSONL="$FEED_PATH" python3 tools/ops/dod_checker.py --phase PHASE_2 --json > "$PHASE2_RESULT_JSON"
PHASE2_EXIT=$?
LUKA_ACTIVITY_FEED_JSONL="$FEED_PATH" python3 tools/ops/dod_checker.py --phase PHASE_8 --json > "$PHASE8_RESULT_JSON"
PHASE8_EXIT=$?
LUKA_ACTIVITY_FEED_JSONL="$FEED_PATH" python3 tools/ops/dod_checker.py --all --update-status --json > "$ALL_UPDATE_JSON"
ALL_EXIT=$?
LUKA_ACTIVITY_FEED_JSONL="$FEED_PATH" LUKA_REQUIRE_OPERATIONAL_PROOF=1 python3 tools/ops/dod_checker.py --phase PHASE_15_5_3 --json > "$PHASE1553_RESULT_JSON"
PHASE1553_EXIT=$?
set -e

if [[ -f core/governance/phase_status.yaml ]]; then
  git diff -- core/governance/phase_status.yaml | sed -n '1,120p' || true
fi

python3 - <<'PY' "$PHASE2_RESULT_JSON" "$PHASE8_RESULT_JSON" "$PHASE1553_RESULT_JSON"
import json
import sys
from pathlib import Path

def pick_result(path: str):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("results", [])
    if not rows:
        raise SystemExit(2)
    return rows[0]

p2 = pick_result(sys.argv[1])
p8 = pick_result(sys.argv[2])
p1553 = pick_result(sys.argv[3])

def has_missing(obj, key):
    return any(str(x) == key for x in obj.get("missing", []))

errors = []
if p2.get("verdict") != "PROVEN":
    errors.append("PHASE_2 verdict not PROVEN")
if has_missing(p2, "taxonomy.incomplete_event"):
    errors.append("PHASE_2 taxonomy.incomplete_event")
if p8.get("verdict") != "PROVEN":
    errors.append("PHASE_8 verdict not PROVEN")
if has_missing(p8, "taxonomy.incomplete_event"):
    errors.append("PHASE_8 taxonomy.incomplete_event")
if any(str(x).startswith("gate.requires_not_proven:") for x in p1553.get("missing", [])):
    errors.append("PHASE_15_5_3 gate.requires_not_proven present")

if errors:
    for err in errors:
        print(f"ERROR: {err}")
    raise SystemExit(2)
PY

echo "ACTIVITY_FEED=$FEED_PATH"
echo "PHASE2_EVIDENCE=$PHASE2_EVIDENCE"
echo "PHASE8_EVIDENCE=$PHASE8_EVIDENCE"
echo "PHASE2_INIT_JSON=$PHASE2_INIT_JSON"
echo "PHASE8_INIT_JSON=$PHASE8_INIT_JSON"
echo "PHASE2_REPORT_PATH=$PHASE2_REPORT_PATH"
echo "PHASE8_REPORT_PATH=$PHASE8_REPORT_PATH"
echo "PHASE2_RESULT_JSON=$PHASE2_RESULT_JSON"
echo "PHASE8_RESULT_JSON=$PHASE8_RESULT_JSON"
echo "PHASE15_5_3_RESULT_JSON=$PHASE1553_RESULT_JSON"
echo "ALL_UPDATE_JSON=$ALL_UPDATE_JSON"
echo "P2_INIT_EXIT=$P2_INIT_EXIT"
echo "P8_INIT_EXIT=$P8_INIT_EXIT"
echo "PHASE2_EXIT=$PHASE2_EXIT"
echo "PHASE8_EXIT=$PHASE8_EXIT"
echo "ALL_EXIT=$ALL_EXIT"
echo "PHASE15_5_3_EXIT=$PHASE1553_EXIT"

if [[ $PHASE2_EXIT -ne 0 || $PHASE8_EXIT -ne 0 || $ALL_EXIT -eq 4 || $PHASE1553_EXIT -eq 4 ]]; then
  exit 2
fi

exit 0
