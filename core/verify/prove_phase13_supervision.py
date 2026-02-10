#!/usr/bin/env python3
"""Phase 13 proof runner: supervision annotation loop + PROVEN provenance row."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
ANNOTATION_HANDLER = ROOT / "tools" / "ops" / "mission_control" / "annotation_handler.py"


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to import: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def _hash(obj: object) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def run_proof() -> bool:
    mod = _load_module(ANNOTATION_HANDLER, "annotation_handler_proof")

    # real repo sink
    old_root = os.environ.get("ROOT")
    old_0 = os.environ.get("0LUKA_ROOT")
    os.environ["ROOT"] = str(ROOT)
    os.environ["0LUKA_ROOT"] = str(ROOT)
    try:
        row = mod.append_annotation(
            {
                "event_id": "phase13-proof",
                "action": "note",
                "comment": "phase13 proof annotation",
                "author": "phase13_auditor",
                "ts": _utc_now(),
            }
        )
    finally:
        if old_root is None:
            os.environ.pop("ROOT", None)
        else:
            os.environ["ROOT"] = old_root
        if old_0 is None:
            os.environ.pop("0LUKA_ROOT", None)
        else:
            os.environ["0LUKA_ROOT"] = old_0

    anno_path = ROOT / "observability" / "annotations" / "annotations.jsonl"
    if not anno_path.exists():
        print("proof fail: missing annotations sink")
        return False

    last_line = [x for x in anno_path.read_text(encoding="utf-8").splitlines() if x.strip()][-1]
    stored = json.loads(last_line)
    if stored.get("event_id") != "phase13-proof":
        print("proof fail: annotation write mismatch")
        return False

    from core.run_provenance import append_event, append_provenance

    proof = {
        "phase": "13",
        "status": "PROVEN",
        "annotation_ref": str(anno_path),
        "event_id": row.get("event_id"),
    }

    prov_row = {
        "schema_version": "run_provenance_v1",
        "author": "phase13-proof-runner",
        "tool": "Phase13ProofRunner",
        "input_hash": _hash({"event_id": "phase13-proof", "action": "note"}),
        "output_hash": _hash(proof),
        "ts": _utc_now(),
        "evidence_refs": [
            "command:python3 core/verify/prove_phase13_supervision.py",
            "file:observability/annotations/annotations.jsonl",
            "file:tools/ops/mission_control/annotation_handler.py",
        ],
    }
    append_provenance(prov_row)
    append_event(
        {
            "type": "phase13.verified",
            "category": "policy",
            "phase": "13",
            "status": "PROVEN",
            "annotation_event_id": "phase13-proof",
        }
    )
    return True


def main() -> int:
    ok = run_proof()
    print("Phase 13 Proof result:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
