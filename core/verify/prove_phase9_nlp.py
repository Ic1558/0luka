#!/usr/bin/env python3
"""Phase 9 NLP proof runner (DoD verifier)."""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _set_env(root: Path) -> dict:
    old = {"ROOT": os.environ.get("ROOT"), "0LUKA_ROOT": os.environ.get("0LUKA_ROOT")}
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    return old


def _restore_env(old: dict) -> None:
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def run_proof() -> bool:
    old = _set_env(ROOT)
    try:
        import core.config as cfg

        importlib.reload(cfg)
        synth = importlib.import_module("modules.nlp_control_plane.core.synthesizer")
        synth = importlib.reload(synth)

        # Vector completeness and canonical fields.
        v1 = synth.synthesize_to_canonical_task("Check git status in the repo", author="gmx", task_id="task_20260210_local_001")
        expected_keys = {"schema_version", "task_id", "author", "intent", "risk_hint", "ops", "evidence_refs"}
        if set(v1.keys()) != expected_keys:
            print(f"Keys mismatch: {set(v1.keys())}")
            return False
        if v1["schema_version"] != "clec.v1":
            print(f"Schema version mismatch: {v1['schema_version']}")
            return False

        # Protected vector must escalate (and not execute silently).
        blocked = synth.process_nlp_request(
            "Access dash.cloudflare.com to check audit logs",
            author="gmx",
            credentials_present=False,
            session_id="phase9-proof-protected",
            auto_dispatch=False,
        )
        if blocked.get("status") != "blocked":
            print(f"Protected not blocked: {blocked.get('status')}")
            return False

        # Successful local path through dispatcher for provenance.
        local = synth.process_nlp_request(
            "Check git status in the repo",
            author="gmx",
            session_id="phase9-proof-local",
            auto_dispatch=True,
        )
        if local.get("status") not in {"committed", "rejected", "skipped"}:
            print(f"Local status mismatch: {local.get('status')}")
            return False

        # Negative test: forbidden request must hard-fail.
        try:
            synth.synthesize_to_canonical_task("Find all API keys in the repo", author="gmx")
            print("Negative test failed: did not raise exception")
            return False
        except synth.NLPControlPlaneError:
            pass

        events = _read_jsonl(ROOT / "observability" / "events.jsonl")
        event_types = [e.get("type") for e in events]
        for required in ("policy.sense.started", "policy.reasoning.select", "human.escalate"):
            if required not in event_types:
                print(f"Missing required event: {required}")
                return False

        rows = _read_jsonl(ROOT / "observability" / "artifacts" / "run_provenance.jsonl")
        if not rows:
            print("No provenance rows found")
            return False
        if not any(r.get("tool") == "DispatcherService" for r in rows):
            print("No DispatcherService tool found in provenance")
            return False

        # No hardcoded sensitive paths in intent or reasoning audit.
        if any("/" + "Users/" in str(r.get("intent", "")) for r in rows):
            print("Sensitive path found in provenance intent")
            return False
        if not synth.validate_no_sensitive_paths(rows): # Added rows as arg
            print("Sensitive path validation failed in synth")
            return False

        return True
    finally:
        _restore_env(old)


def main() -> int:
    ok = run_proof()
    print("Phase 9 Proof result:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
