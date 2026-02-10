#!/usr/bin/env python3
"""Phase 14 proof runner: collector end-to-end + provenance row."""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import hashlib
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
COLLECTOR_PATH = ROOT / "tools" / "ops" / "learning_metrics" / "collector.py"
FIXTURE_PATH = ROOT / "core" / "verify" / "fixtures" / "phase14_mock_logs.jsonl"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _hash(obj: object) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_collector():
    spec = importlib.util.spec_from_file_location("phase14_collector", COLLECTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load collector")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def _write_fixture_inputs(root: Path) -> None:
    activity_path = root / "observability" / "activity" / "activity.jsonl"
    ann_path = root / "observability" / "annotations" / "annotations.jsonl"
    activity_path.parent.mkdir(parents=True, exist_ok=True)
    ann_path.parent.mkdir(parents=True, exist_ok=True)

    acts = []
    anns = []
    for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        kind = row.pop("kind")
        if kind == "activity":
            acts.append(row)
        else:
            anns.append(row)
    activity_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in acts) + "\n", encoding="utf-8")
    ann_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in anns) + "\n", encoding="utf-8")


def run_proof() -> bool:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        old_root = os.environ.get("ROOT")
        old_0 = os.environ.get("0LUKA_ROOT")
        os.environ["ROOT"] = str(root)
        os.environ["0LUKA_ROOT"] = str(root)
        try:
            _write_fixture_inputs(root)
            collector = _load_collector()
            out = collector.collect_metrics()

            metrics_file = root / "observability" / "metrics" / "phase14" / "system_kpis.jsonl"
            recs_file = root / "observability" / "recommendations" / "policy_suggestions.jsonl"
            if not metrics_file.exists() or not recs_file.exists():
                print("proof fail: missing output files")
                return False

            if out.get("alignment_rate") != 33.33 or out.get("block_rate") != 33.33:
                print("proof fail: unexpected kpi values")
                return False
        finally:
            if old_root is None:
                os.environ.pop("ROOT", None)
            else:
                os.environ["ROOT"] = old_root
            if old_0 is None:
                os.environ.pop("0LUKA_ROOT", None)
            else:
                os.environ["0LUKA_ROOT"] = old_0

    # record PROVEN in real run_provenance
    from core.run_provenance import append_provenance, append_event

    summary = {
        "phase": "14",
        "status": "PROVEN",
        "collector": "tools/ops/learning_metrics/collector.py",
    }
    row = {
        "schema_version": "run_provenance_v1",
        "author": "phase14-proof-runner",
        "tool": "Phase14ProofRunner",
        "input_hash": _hash({"fixture": str(FIXTURE_PATH)}),
        "output_hash": _hash(summary),
        "ts": _utc_now(),
        "evidence_refs": [
            "command:python3 core/verify/prove_phase14_learning_metrics.py",
            "file:tools/ops/learning_metrics/collector.py",
            "file:core/verify/fixtures/phase14_mock_logs.jsonl",
        ],
    }
    append_provenance(row)
    append_event({"type": "phase14.verified", "category": "policy", "phase": "14", "status": "PROVEN"})
    return True


def main() -> int:
    ok = run_proof()
    print("Phase 14 Proof result:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
