#!/usr/bin/env python3
from __future__ import annotations

import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.clec_executor import execute_clec_ops
from core.phase1a_resolver import Phase1AResolverError, gate_inbound_envelope


def _base_envelope() -> dict:
    return {
        "v": "0luka.envelope/v1",
        "type": "task.request",
        "trace": {"trace_id": "tr_clec_001", "ts": "2026-02-08T00:00:00Z"},
        "source": {"actor": "openwork", "lane": "run"},
        "payload": {
            "task": {
                "schema_version": "clec.v1",
                "task_id": "clec0001",
                "ts_utc": "2026-02-08T00:00:00Z",
                "author": "lisa",
                "call_sign": "[Lisa]",
                "root": "${HOME}/0luka",
                "intent": "clec.execute",
                "ops": [{"op_id": "op1", "type": "run", "command": "git status"}],
                "verify": [{"check": "gate.test.run", "target": "core/verify", "command": "python3 core/verify/test_ref_resolver.py"}],
            }
        },
    }


def test_valid_clec_passes() -> None:
    out = gate_inbound_envelope(_base_envelope())
    assert out["payload"]["task"]["resolved"]["trust"] is True


def test_invalid_op_rejected() -> None:
    env = _base_envelope()
    env["payload"]["task"]["ops"][0]["type"] = "rm_rf"
    try:
        gate_inbound_envelope(env)
    except Phase1AResolverError as exc:
        assert "clec_schema_validation_failed" in str(exc)
        return
    raise AssertionError("invalid op type was not rejected")


def test_unauthorized_run_blocked() -> None:
    env = _base_envelope()
    env["payload"]["task"]["ops"][0]["command"] = "echo blocked"
    try:
        gate_inbound_envelope(env)
    except Phase1AResolverError as exc:
        assert "unauthorized run command" in str(exc)
        return
    raise AssertionError("unauthorized run command was not rejected")


def test_evidence_capture() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "repo").mkdir(parents=True, exist_ok=True)
        (root / "repo/.git").mkdir(parents=True, exist_ok=True)
        ops = [
            {"op_id": "w1", "type": "write_text", "target_path": "tmp/out.txt", "content": "hello"},
            {"op_id": "r1", "type": "run", "command": "git status"},
        ]
        # run from real repo root; write_text evidence/hash must still be captured
        status, evidence = execute_clec_ops(
            ops,
            {},
            run_provenance={
                "task_id": "clec_gate_evidence",
                "author": "test",
                "tool": "CLECExecutor",
                "evidence_refs": ["test:clec_gate"],
            },
        )
        assert status in {"ok", "partial"}
        assert evidence.get("hashes"), "write_text must capture hashes"
        assert evidence.get("logs"), "run must capture stdout/stderr logs"


if __name__ == "__main__":
    test_valid_clec_passes()
    test_invalid_op_rejected()
    test_unauthorized_run_blocked()
    test_evidence_capture()
    print("ok")
