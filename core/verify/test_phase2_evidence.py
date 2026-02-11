#!/usr/bin/env python3
"""Phase 2: RunProvenance evidence enforcement tests."""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _set_env(root: Path) -> dict:
    old = {"ROOT": os.environ.get("ROOT"), "0LUKA_ROOT": os.environ.get("0LUKA_ROOT")}
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    return old


def _restore_env(old: dict) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def _load_modules():
    import core.config as cfg

    importlib.reload(cfg)
    rp = importlib.import_module("core.run_provenance")
    ex = importlib.import_module("core.clec_executor")
    return importlib.reload(rp), importlib.reload(ex)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def test_missing_provenance_hard_fails() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _rp, ex = _load_modules()
            try:
                ex.execute_clec_ops(
                    [{"op_id": "w1", "type": "write_text", "target_path": "tmp/out.txt", "content": "a"}],
                    {},
                )
                raise AssertionError("missing provenance must hard fail")
            except ex.CLECExecutorError as exc:
                assert "run_provenance_required" in str(exc)

            events = _read_jsonl(root / "observability" / "events.jsonl")
            assert any(e.get("type") == "execution.failed" for e in events)
            print("test_missing_provenance_hard_fails: ok")
        finally:
            _restore_env(old)


def test_deterministic_hash_for_same_input() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            rp, ex = _load_modules()
            ops = [{"op_id": "w1", "type": "write_text", "target_path": "tmp/out.txt", "content": "a"}]

            p1 = {"task_id": "t1", "author": "tester", "tool": "CLECExecutor", "evidence_refs": ["e1"]}
            p2 = {"task_id": "t2", "author": "tester", "tool": "CLECExecutor", "evidence_refs": ["e2"]}

            ex.execute_clec_ops(ops, {}, run_provenance=p1)
            ex.execute_clec_ops(ops, {}, run_provenance=p2)

            rows = _read_jsonl(root / "observability" / "artifacts" / "run_provenance.jsonl")
            assert len(rows) >= 2
            assert rows[-1]["input_hash"] == rows[-2]["input_hash"]
            expected = rp.canonical_hash({"ops": ops, "verify": []})
            assert rows[-1]["input_hash"] == expected
            print("test_deterministic_hash_for_same_input: ok")
        finally:
            _restore_env(old)


def test_execution_events_and_append_only_artifact() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _rp, ex = _load_modules()
            prov = {
                "task_id": "evt1",
                "author": "tester",
                "tool": "CLECExecutor",
                "evidence_refs": ["test:phase2"],
            }
            ex.execute_clec_ops(
                [{"op_id": "w1", "type": "write_text", "target_path": "tmp/out.txt", "content": "a"}],
                {},
                run_provenance=prov,
            )

            events = _read_jsonl(root / "observability" / "events.jsonl")
            assert any(e.get("type") == "execution.started" for e in events)
            assert any(e.get("type") == "execution.completed" for e in events)

            rows = _read_jsonl(root / "observability" / "artifacts" / "run_provenance.jsonl")
            assert len(rows) >= 1
            last = rows[-1]
            for key in ("author", "tool", "input_hash", "output_hash", "ts", "evidence_refs"):
                assert key in last
            print("test_execution_events_and_append_only_artifact: ok")
        finally:
            _restore_env(old)


def main() -> int:
    test_missing_provenance_hard_fails()
    test_deterministic_hash_for_same_input()
    test_execution_events_and_append_only_artifact()
    print("test_phase2_evidence: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
