from __future__ import annotations

import json
from pathlib import Path

from tools.ops.audit_segment_chain import audit_segment_chain
from tools.ops.segment_chain_append import GENESIS_PREV_CHAIN_HASH, append_segment_chain


def _h(ch: str) -> str:
    return ch * 64


def _setup_runtime(tmp_path: Path) -> tuple[Path, Path, Path]:
    runtime_root = tmp_path / "runtime"
    logs_dir = runtime_root / "logs"
    archive_dir = logs_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return runtime_root, logs_dir, archive_dir


def _write_segment(archive_dir: Path, segment_name: str, line_count: int = 2) -> None:
    lines = []
    for i in range(line_count):
        lines.append(json.dumps({"hash": _h("a"), "line": i}, separators=(",", ":")))
    (archive_dir / segment_name).write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_registry(logs_dir: Path, segment_name: str, seal_hash: str) -> None:
    rec = {
        "segment_name": segment_name,
        "seal_hash": seal_hash,
        "first_hash": _h("a"),
        "last_hash": _h("b"),
        "line_count": 2,
        "sealed_at_utc": "2026-03-06T00:00:00Z",
        "registry_ts_utc": "2026-03-06T00:00:00Z",
    }
    with (logs_dir / "rotation_registry.jsonl").open("a", encoding="utf-8") as out:
        out.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")


def test_segment_chain_genesis_append(tmp_path: Path) -> None:
    runtime_root, logs_dir, archive_dir = _setup_runtime(tmp_path)
    # Ensure the helper can run even when the root already exists.
    _write_segment(archive_dir, "activity_feed.20260306T000000Z.jsonl")
    _append_registry(logs_dir, "activity_feed.20260306T000000Z.jsonl", _h("1"))

    ok, record, error = append_segment_chain(
        runtime_root,
        segment_name="activity_feed.20260306T000000Z.jsonl",
        seal_hash=_h("1"),
        line_count=2,
        last_hash=_h("2"),
        segment_seq=1,
        prev_chain_hash=GENESIS_PREV_CHAIN_HASH,
    )

    assert ok, error
    assert record is not None
    assert record["segment_seq"] == 1
    assert record["prev_chain_hash"] == GENESIS_PREV_CHAIN_HASH

    report = audit_segment_chain(logs_dir)
    assert report["ok"] is True
    assert report["entries_total"] == 1


def test_segment_chain_continuity_two_entries(tmp_path: Path) -> None:
    runtime_root, logs_dir, archive_dir = _setup_runtime(tmp_path)
    _write_segment(archive_dir, "activity_feed.20260306T000000Z.jsonl")
    _write_segment(archive_dir, "activity_feed.20260306T001000Z.jsonl")
    _append_registry(logs_dir, "activity_feed.20260306T000000Z.jsonl", _h("1"))
    _append_registry(logs_dir, "activity_feed.20260306T001000Z.jsonl", _h("3"))

    ok1, rec1, err1 = append_segment_chain(
        runtime_root,
        segment_name="activity_feed.20260306T000000Z.jsonl",
        seal_hash=_h("1"),
        line_count=2,
        last_hash=_h("2"),
        segment_seq=1,
        prev_chain_hash=GENESIS_PREV_CHAIN_HASH,
    )
    assert ok1, err1
    assert rec1 is not None

    ok2, rec2, err2 = append_segment_chain(
        runtime_root,
        segment_name="activity_feed.20260306T001000Z.jsonl",
        seal_hash=_h("3"),
        line_count=2,
        last_hash=_h("4"),
        segment_seq=2,
        prev_chain_hash=rec1["chain_hash"],
    )
    assert ok2, err2
    assert rec2 is not None

    report = audit_segment_chain(logs_dir)
    assert report["ok"] is True
    assert report["entries_total"] == 2


def test_duplicate_segment_rejected(tmp_path: Path) -> None:
    runtime_root, logs_dir, archive_dir = _setup_runtime(tmp_path)
    segment = "activity_feed.20260306T010000Z.jsonl"
    _write_segment(archive_dir, segment)
    _append_registry(logs_dir, segment, _h("5"))

    ok, _, _ = append_segment_chain(
        runtime_root,
        segment_name=segment,
        seal_hash=_h("5"),
        line_count=2,
        last_hash=_h("6"),
        segment_seq=1,
        prev_chain_hash=GENESIS_PREV_CHAIN_HASH,
    )
    assert ok is True

    ok2, _, err2 = append_segment_chain(
        runtime_root,
        segment_name=segment,
        seal_hash=_h("7"),
        line_count=2,
        last_hash=_h("8"),
        segment_seq=2,
        prev_chain_hash=None,
    )
    assert ok2 is False
    assert err2 == "duplicate_segment"


def test_duplicate_seal_rejected(tmp_path: Path) -> None:
    runtime_root, logs_dir, archive_dir = _setup_runtime(tmp_path)
    seg1 = "activity_feed.20260306T020000Z.jsonl"
    seg2 = "activity_feed.20260306T021000Z.jsonl"
    _write_segment(archive_dir, seg1)
    _write_segment(archive_dir, seg2)
    _append_registry(logs_dir, seg1, _h("9"))
    _append_registry(logs_dir, seg2, _h("9"))

    ok, rec, _ = append_segment_chain(
        runtime_root,
        segment_name=seg1,
        seal_hash=_h("9"),
        line_count=2,
        last_hash=_h("a"),
        segment_seq=1,
        prev_chain_hash=GENESIS_PREV_CHAIN_HASH,
    )
    assert ok is True
    assert rec is not None

    ok2, _, err2 = append_segment_chain(
        runtime_root,
        segment_name=seg2,
        seal_hash=_h("9"),
        line_count=2,
        last_hash=_h("b"),
        segment_seq=2,
        prev_chain_hash=rec["chain_hash"],
    )
    assert ok2 is False
    assert err2 == "duplicate_seal_hash"


def test_chain_fork_and_seq_mismatch_rejected(tmp_path: Path) -> None:
    runtime_root, logs_dir, archive_dir = _setup_runtime(tmp_path)
    seg1 = "activity_feed.20260306T030000Z.jsonl"
    seg2 = "activity_feed.20260306T031000Z.jsonl"
    _write_segment(archive_dir, seg1)
    _write_segment(archive_dir, seg2)
    _append_registry(logs_dir, seg1, _h("c"))
    _append_registry(logs_dir, seg2, _h("d"))

    ok1, rec1, _ = append_segment_chain(
        runtime_root,
        segment_name=seg1,
        seal_hash=_h("c"),
        line_count=2,
        last_hash=_h("d"),
        segment_seq=1,
        prev_chain_hash=GENESIS_PREV_CHAIN_HASH,
    )
    assert ok1 is True
    assert rec1 is not None

    ok2, _, err2 = append_segment_chain(
        runtime_root,
        segment_name=seg2,
        seal_hash=_h("d"),
        line_count=2,
        last_hash=_h("e"),
        segment_seq=5,
        prev_chain_hash=rec1["chain_hash"],
    )
    assert ok2 is False
    assert err2 == "segment_seq_mismatch"

    ok3, _, err3 = append_segment_chain(
        runtime_root,
        segment_name=seg2,
        seal_hash=_h("d"),
        line_count=2,
        last_hash=_h("e"),
        segment_seq=2,
        prev_chain_hash=_h("f"),
    )
    assert ok3 is False
    assert err3 == "chain_fork_detected"


def test_invalid_segment_name_rejected(tmp_path: Path) -> None:
    runtime_root, _, _ = _setup_runtime(tmp_path)
    ok, _, err = append_segment_chain(
        runtime_root,
        segment_name="../bad.jsonl",
        seal_hash=_h("1"),
        line_count=1,
        last_hash=_h("2"),
        segment_seq=1,
        prev_chain_hash=GENESIS_PREV_CHAIN_HASH,
    )
    assert ok is False
    assert err == "invalid_segment_name"


def test_audit_detects_chain_hash_mismatch(tmp_path: Path) -> None:
    runtime_root, logs_dir, archive_dir = _setup_runtime(tmp_path)
    seg1 = "activity_feed.20260306T040000Z.jsonl"
    seg2 = "activity_feed.20260306T041000Z.jsonl"
    _write_segment(archive_dir, seg1)
    _write_segment(archive_dir, seg2)
    _append_registry(logs_dir, seg1, _h("1"))
    _append_registry(logs_dir, seg2, _h("3"))

    ok1, rec1, _ = append_segment_chain(
        runtime_root,
        segment_name=seg1,
        seal_hash=_h("1"),
        line_count=2,
        last_hash=_h("2"),
        segment_seq=1,
        prev_chain_hash=GENESIS_PREV_CHAIN_HASH,
    )
    assert ok1 and rec1 is not None
    ok2, _, _ = append_segment_chain(
        runtime_root,
        segment_name=seg2,
        seal_hash=_h("3"),
        line_count=2,
        last_hash=_h("4"),
        segment_seq=2,
        prev_chain_hash=rec1["chain_hash"],
    )
    assert ok2

    chain_path = logs_dir / "segment_chain.jsonl"
    rows = [json.loads(line) for line in chain_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[1]["chain_hash"] = _h("0")
    chain_path.write_text("\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n", encoding="utf-8")

    report = audit_segment_chain(logs_dir)
    assert report["ok"] is False
    assert report["first_failure"] == "chain_hash_mismatch"


def test_audit_detects_missing_registry_entry(tmp_path: Path) -> None:
    runtime_root, logs_dir, archive_dir = _setup_runtime(tmp_path)
    seg1 = "activity_feed.20260306T050000Z.jsonl"
    _write_segment(archive_dir, seg1)

    ok, _, _ = append_segment_chain(
        runtime_root,
        segment_name=seg1,
        seal_hash=_h("7"),
        line_count=2,
        last_hash=_h("8"),
        segment_seq=1,
        prev_chain_hash=GENESIS_PREV_CHAIN_HASH,
    )
    assert ok

    report = audit_segment_chain(logs_dir)
    assert report["ok"] is False
    assert report["first_failure"] == "missing_registry_entry"


def test_audit_detects_missing_segment_file(tmp_path: Path) -> None:
    runtime_root, logs_dir, archive_dir = _setup_runtime(tmp_path)
    seg1 = "activity_feed.20260306T060000Z.jsonl"
    _write_segment(archive_dir, seg1)
    _append_registry(logs_dir, seg1, _h("9"))

    ok, _, _ = append_segment_chain(
        runtime_root,
        segment_name=seg1,
        seal_hash=_h("9"),
        line_count=2,
        last_hash=_h("a"),
        segment_seq=1,
        prev_chain_hash=GENESIS_PREV_CHAIN_HASH,
    )
    assert ok

    (archive_dir / seg1).unlink()
    report = audit_segment_chain(logs_dir)
    assert report["ok"] is False
    assert report["first_failure"] == "missing_segment_file"
