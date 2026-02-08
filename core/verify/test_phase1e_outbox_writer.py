from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core.outbox_writer import OutboxWriterError, write_result_to_outbox


def _base_result() -> dict:
    return {
        "task_id": "phase1e_writer_ok",
        "status": "ok",
        "summary": "writer smoke",
        "outputs": {"json": {"ok": True}, "artifacts": []},
        "evidence": {"logs": ["done"], "commands": ["noop"]},
        "provenance": {"hashes": {"inputs_sha256": "a", "outputs_sha256": "b"}},
    }


def _assert_raises(fn, expected):
    try:
        fn()
    except expected:
        return
    raise AssertionError(f"expected {expected.__name__}")


def test_atomic_write_and_schema() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["0LUKA_ROOT"] = str(root)
        (root / "interface/outbox").mkdir(parents=True, exist_ok=True)
        map_path = root / "map.yaml"
        map_path.write_text(
            "version: '1'\n"
            "hosts:\n"
            "  default:\n"
            "    root: '${0LUKA_ROOT}'\n"
            "refs:\n"
            "  'ref://interface/outbox': '${root}/interface/outbox'\n",
            encoding="utf-8",
        )
        out_path, envelope = write_result_to_outbox(_base_result(), ref_map_path=str(map_path))
        assert out_path.exists(), out_path
        loaded = json.loads(out_path.read_text(encoding="utf-8"))
        assert loaded["v"] == "0luka.result/v1"
        assert loaded["task_id"] == "phase1e_writer_ok"
        assert envelope["status"] == "ok"


def test_missing_status_reject() -> None:
    bad = _base_result()
    bad.pop("status")
    _assert_raises(lambda: write_result_to_outbox(bad), OutboxWriterError)


def test_ok_without_evidence_becomes_partial() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        os.environ["0LUKA_ROOT"] = str(root)
        (root / "interface/outbox").mkdir(parents=True, exist_ok=True)
        map_path = root / "map.yaml"
        map_path.write_text(
            "version: '1'\n"
            "hosts:\n"
            "  default:\n"
            "    root: '${0LUKA_ROOT}'\n"
            "refs:\n"
            "  'ref://interface/outbox': '${root}/interface/outbox'\n",
            encoding="utf-8",
        )
        item = _base_result()
        item["task_id"] = "phase1e_partial"
        item["evidence"] = {"logs": [], "commands": []}
        _, env = write_result_to_outbox(item, ref_map_path=str(map_path))
        assert env["status"] == "partial"


def main() -> int:
    os.environ.setdefault("0LUKA_ROOT", str(Path(__file__).resolve().parents[2]))
    test_atomic_write_and_schema()
    test_missing_status_reject()
    test_ok_without_evidence_becomes_partial()
    print("test_phase1e_outbox_writer: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
