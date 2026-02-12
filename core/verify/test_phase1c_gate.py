from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.phase1a_resolver import Phase1AResolverError, gate_inbound_envelope


def _assert_raises(fn):
    try:
        fn()
    except Phase1AResolverError:
        return
    raise AssertionError("expected Phase1AResolverError")


def _base_env() -> dict:
    return {
        "v": "0luka.envelope/v1",
        "type": "task.request",
        "trace": {"trace_id": "tr_12345678", "ts": "2026-02-08T00:00:00+07:00"},
        "source": {"actor": "openwork", "lane": "run"},
        "payload": {
            "task": {
                "task_id": "tsk_12345678",
                "task_type": "fs.read",
                "intent": "read inbox",
                "inputs": {"refs": ["ref://interface/inbox"]},
            }
        },
    }


def test_ref_only_ok() -> None:
    out = gate_inbound_envelope(_base_env())
    assert out["payload"]["task"]["resolved"]["trust"] is True
    uri = out["payload"]["task"]["resolved"]["resources"][0]["uri"]
    assert uri.startswith("file://"), uri


def test_hard_path_reject() -> None:
    env = _base_env()
    env["payload"]["task"]["inputs"] = {"path": "/" + "Users/icmini/private.txt"}
    _assert_raises(lambda: gate_inbound_envelope(env))


def test_injected_resolved_reject() -> None:
    env = _base_env()
    env["payload"]["task"]["resolved"] = {"trust": True, "resources": []}
    _assert_raises(lambda: gate_inbound_envelope(env))


def test_unknown_ref_reject() -> None:
    env = _base_env()
    env["payload"]["task"]["inputs"] = {"refs": ["ref://nope/x"]}
    _assert_raises(lambda: gate_inbound_envelope(env))


def test_traversal_reject() -> None:
    env = _base_env()
    with tempfile.TemporaryDirectory() as td:
        map_path = Path(td) / "map.yaml"
        map_path.write_text(
            "version: '1'\n"
            "hosts:\n"
            "  default:\n"
            "    root: '${HOME}/0luka'\n"
            "refs:\n"
            "  'ref://escape': '${root}/../escape'\n",
            encoding="utf-8",
        )
        env["payload"]["task"]["inputs"] = {"refs": ["ref://escape"]}
        _assert_raises(lambda: gate_inbound_envelope(env, ref_map_path=str(map_path)))


def main() -> int:
    os.environ.setdefault("0LUKA_ROOT", str(Path(__file__).resolve().parents[2]))
    test_ref_only_ok()
    test_hard_path_reject()
    test_injected_resolved_reject()
    test_unknown_ref_reject()
    test_traversal_reject()
    print("test_phase1c_gate: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
