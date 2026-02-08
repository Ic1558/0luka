from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.phase1d_result_gate import ResultGateError, gate_outbound_result


def _base_result() -> dict:
    return {
        "task_id": "tk_1",
        "status": "ok",
        "summary": "done",
        "outputs": {"artifacts": []},
        "evidence": {"commands": [], "effects": [], "logs": []},
        "provenance": {"hashes": {}},
    }


def _assert_raises(fn, expected):
    try:
        fn()
    except expected:
        return
    raise AssertionError(f"expected {expected.__name__}")


def test_ok_plain() -> None:
    out = gate_outbound_result(_base_result())
    assert out["status"] == "ok"


def test_redact_users_log() -> None:
    result = _base_result()
    result["evidence"]["logs"] = ["read /Users/icmini/private.txt"]
    out = gate_outbound_result(result)
    assert "/Users/" not in str(out)
    assert "<redacted:path>" in str(out)


def test_side_effect_without_evidence_fail_closed() -> None:
    result = _base_result()
    result["evidence"]["commands"] = ["proc.run"]
    out = gate_outbound_result(result)
    assert out["status"] == "error"
    assert out.get("reason") == "missing_evidence_for_side_effect"


def test_error_message_sanitized() -> None:
    result = _base_result()
    result["status"] = "error"
    result["error"] = "failed at /Users/icmini/a.py"
    out = gate_outbound_result(result)
    assert "/Users/" not in str(out)
    assert isinstance(out.get("error"), dict)


def test_back_resolve_trusted_uri() -> None:
    root = Path(__file__).resolve().parents[2]
    result = _base_result()
    result["resolved"] = {
        "trust": True,
        "resources": [{"kind": "path", "uri": (root / "interface/inbox").as_uri()}],
    }
    result["evidence"]["logs"] = [f"used {(root / 'interface/inbox').as_uri()}"]
    out = gate_outbound_result(result)
    assert "ref://interface/inbox" in str(out)
    assert "file:///Users/" not in str(out)


def test_schema_missing_task_id_reject() -> None:
    result = _base_result()
    result.pop("task_id")
    _assert_raises(lambda: gate_outbound_result(result), ResultGateError)


def main() -> int:
    os.environ.setdefault("0LUKA_ROOT", str(Path(__file__).resolve().parents[2]))
    test_ok_plain()
    test_redact_users_log()
    test_side_effect_without_evidence_fail_closed()
    test_error_message_sanitized()
    test_back_resolve_trusted_uri()
    test_schema_missing_task_id_reject()
    print("test_phase1d_result_gate: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
