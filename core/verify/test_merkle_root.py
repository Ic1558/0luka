from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.build_merkle_root import (
    SegmentChainError,
    build_ledger_root_payload,
    compute_leaf_hashes,
    compute_merkle_root,
    write_ledger_root,
)
from tools.ops.ledger_verify import verify_ledger, verify_ledger_root
from tools.ops.segment_chain_append import GENESIS_PREV_CHAIN_HASH, append_segment_chain


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _setup_runtime(tmp_path: Path) -> tuple[Path, Path, Path]:
    runtime_root = tmp_path / "runtime"
    logs_dir = runtime_root / "logs"
    archive_dir = logs_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    return runtime_root, logs_dir, archive_dir


def _write_active_feed(logs_dir: Path) -> str:
    line = json.dumps({"action": "noop", "hash": _sha("feed-line-1")}, sort_keys=True, separators=(",", ":"))
    path = logs_dir / "activity_feed.jsonl"
    path.write_text(line + "\n", encoding="utf-8")
    return line


def _write_segment(archive_dir: Path, segment_name: str) -> tuple[str, str, int]:
    first_hash = _sha(f"{segment_name}:1")
    last_hash = _sha(f"{segment_name}:2")
    rows = [
        {"hash": first_hash, "action": "segment_open"},
        {"hash": last_hash, "prev_hash": first_hash, "action": "segment_close"},
    ]
    path = archive_dir / segment_name
    path.write_text(
        "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )
    return first_hash, last_hash, len(rows)


def _append_registry(
    logs_dir: Path,
    *,
    segment_name: str,
    seal_hash: str,
    first_hash: str,
    last_hash: str,
    line_count: int,
) -> None:
    row = {
        "segment_name": segment_name,
        "seal_hash": seal_hash,
        "first_hash": first_hash,
        "last_hash": last_hash,
        "line_count": line_count,
        "sealed_at_utc": "2026-03-07T00:00:00Z",
        "registry_ts_utc": "2026-03-07T00:00:00Z",
    }
    with (logs_dir / "rotation_registry.jsonl").open("a", encoding="utf-8") as out:
        out.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def _write_epoch_manifest(logs_dir: Path, feed_line: str) -> None:
    feed_path = logs_dir / "activity_feed.jsonl"
    row = {
        "epoch_id": 1,
        "prev_epoch_hash": "0" * 64,
        "epoch_hash": "",
        "event": "epoch_marker",
        "ts_utc": "2026-03-07T00:00:00Z",
        "log_heads": {
            "activity_feed": {
                "path": "logs/activity_feed.jsonl",
                "segment": "logs/activity_feed.jsonl",
                "line_count": 1,
                "byte_offset": feed_path.stat().st_size,
                "last_event_hash": _sha(feed_line),
            }
        },
    }
    material = str(row["epoch_id"]) + row["prev_epoch_hash"] + json.dumps(
        row["log_heads"], sort_keys=True, separators=(",", ":")
    )
    row["epoch_hash"] = _sha(material)
    (logs_dir / "epoch_manifest.jsonl").write_text(
        json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _append_chain_entry(
    runtime_root: Path,
    logs_dir: Path,
    archive_dir: Path,
    *,
    segment_name: str,
    segment_seq: int,
    prev_chain_hash: str,
) -> str:
    first_hash, last_hash, line_count = _write_segment(archive_dir, segment_name)
    seal_hash = _sha(f"seal:{segment_name}")
    _append_registry(
        logs_dir,
        segment_name=segment_name,
        seal_hash=seal_hash,
        first_hash=first_hash,
        last_hash=last_hash,
        line_count=line_count,
    )
    ok, record, error = append_segment_chain(
        runtime_root,
        segment_name=segment_name,
        seal_hash=seal_hash,
        line_count=line_count,
        last_hash=last_hash,
        segment_seq=segment_seq,
        prev_chain_hash=prev_chain_hash,
    )
    assert ok, error
    assert record is not None
    return record["chain_hash"]


def _seed_runtime(tmp_path: Path, segment_count: int) -> tuple[Path, Path]:
    runtime_root, logs_dir, archive_dir = _setup_runtime(tmp_path)
    feed_line = _write_active_feed(logs_dir)
    _write_epoch_manifest(logs_dir, feed_line)

    prev_chain_hash = GENESIS_PREV_CHAIN_HASH
    for index in range(1, segment_count + 1):
        prev_chain_hash = _append_chain_entry(
            runtime_root,
            logs_dir,
            archive_dir,
            segment_name=f"activity_feed.20260307T00{index:02d}00Z.jsonl",
            segment_seq=index,
            prev_chain_hash=prev_chain_hash,
        )
    return runtime_root, logs_dir


def test_genesis_root_creation_is_deterministic(tmp_path: Path) -> None:
    _, logs_dir = _seed_runtime(tmp_path, 1)

    payload_a = build_ledger_root_payload(logs_dir, ts_utc="2026-03-07T01:00:00Z")
    payload_b = build_ledger_root_payload(logs_dir, ts_utc="2026-03-07T01:00:00Z")

    assert payload_a["leaf_count"] == 1
    assert payload_a == payload_b
    assert payload_a["merkle_root"] == payload_a["leaf_hashes"][0]


def test_multi_leaf_root_is_stable(tmp_path: Path) -> None:
    _, logs_dir = _seed_runtime(tmp_path, 2)

    payload_a = build_ledger_root_payload(logs_dir, ts_utc="2026-03-07T01:00:00Z")
    payload_b = build_ledger_root_payload(logs_dir, ts_utc="2026-03-07T02:00:00Z")

    assert payload_a["leaf_count"] == 2
    assert payload_a["merkle_root"] == payload_b["merkle_root"]
    assert payload_a["leaf_hashes"] == payload_b["leaf_hashes"]


def test_odd_leaf_duplication_rule(tmp_path: Path) -> None:
    _, logs_dir = _seed_runtime(tmp_path, 3)

    payload = build_ledger_root_payload(logs_dir, ts_utc="2026-03-07T01:00:00Z")
    leaves = compute_leaf_hashes(
        [json.loads(line) for line in (logs_dir / "segment_chain.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    )
    expected = compute_merkle_root(
        [
            _sha(leaves[0] + leaves[1]),
            _sha(leaves[2] + leaves[2]),
        ]
    )

    assert payload["leaf_count"] == 3
    assert payload["merkle_root"] == expected


def test_tampered_chain_hash_fails_verify(tmp_path: Path) -> None:
    runtime_root, logs_dir = _seed_runtime(tmp_path, 2)
    payload = build_ledger_root_payload(logs_dir, ts_utc="2026-03-07T01:00:00Z")
    write_ledger_root(logs_dir / "ledger_root.json", payload)

    chain_path = logs_dir / "segment_chain.jsonl"
    rows = [json.loads(line) for line in chain_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[1]["chain_hash"] = _sha("tampered-chain-hash")
    chain_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )

    report = verify_ledger(runtime_root)

    assert report["ok"] is False
    assert report["checks"]["segment_chain"]["ok"] is False
    root_errors = [entry["error"] for entry in report["checks"]["ledger_root"]["errors"]]
    assert "merkle_root_mismatch" in root_errors


def test_segment_seq_disorder_fails_build(tmp_path: Path) -> None:
    _, logs_dir = _seed_runtime(tmp_path, 2)

    chain_path = logs_dir / "segment_chain.jsonl"
    rows = [json.loads(line) for line in chain_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows[1]["segment_seq"] = 5
    chain_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SegmentChainError, match="segment_seq_mismatch"):
        build_ledger_root_payload(logs_dir)


def test_head_mismatch_fails_verify(tmp_path: Path) -> None:
    runtime_root, logs_dir = _seed_runtime(tmp_path, 2)
    payload = build_ledger_root_payload(logs_dir, ts_utc="2026-03-07T01:00:00Z")
    write_ledger_root(logs_dir / "ledger_root.json", payload)

    root_path = logs_dir / "ledger_root.json"
    stored = json.loads(root_path.read_text(encoding="utf-8"))
    stored["segment_chain_head"] = _sha("stale-head")
    root_path.write_text(json.dumps(stored, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

    report = verify_ledger_root(runtime_root)

    assert report["ok"] is False
    assert report["first_failure"] == "stale_segment_chain_head"


def test_missing_ledger_root_fails_cleanly(tmp_path: Path) -> None:
    runtime_root, _ = _seed_runtime(tmp_path, 1)

    report = verify_ledger_root(runtime_root)

    assert report["ok"] is False
    assert report["first_failure"] == "missing_ledger_root"
