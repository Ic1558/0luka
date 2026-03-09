from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops.export_ledger_proof import export_proof_pack
from tools.ops.segment_chain_append import GENESIS_PREV_CHAIN_HASH, append_segment_chain
from tools.ops.build_merkle_root import build_ledger_root_payload, write_ledger_root


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
    (logs_dir / "activity_feed.jsonl").write_text(line + "\n", encoding="utf-8")
    return line


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


def _write_segment(archive_dir: Path, segment_name: str) -> tuple[str, str, int]:
    first_hash = _sha(f"{segment_name}:1")
    last_hash = _sha(f"{segment_name}:2")
    rows = [
        {"hash": first_hash, "action": "segment_open"},
        {"hash": last_hash, "prev_hash": first_hash, "action": "segment_close"},
    ]
    (archive_dir / segment_name).write_text(
        "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n",
        encoding="utf-8",
    )
    return first_hash, last_hash, len(rows)


def _append_registry(logs_dir: Path, *, segment_name: str, seal_hash: str, first_hash: str, last_hash: str, line_count: int) -> None:
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


def _append_seal(logs_dir: Path, *, segment_name: str, seal_hash: str, first_hash: str, last_hash: str, line_count: int) -> None:
    row = {
        "action": "rotation_seal",
        "segment_name": segment_name,
        "first_hash": first_hash,
        "last_hash": last_hash,
        "line_count": line_count,
        "sealed_at_utc": "2026-03-07T00:00:00Z",
        "seal_hash": seal_hash,
    }
    with (logs_dir / "rotation_seals.jsonl").open("a", encoding="utf-8") as out:
        out.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def _seed_runtime(tmp_path: Path, segment_count: int = 2) -> Path:
    runtime_root, logs_dir, archive_dir = _setup_runtime(tmp_path)
    feed_line = _write_active_feed(logs_dir)
    _write_epoch_manifest(logs_dir, feed_line)

    prev_chain_hash = GENESIS_PREV_CHAIN_HASH
    for index in range(1, segment_count + 1):
        segment_name = f"activity_feed.20260307T00{index:02d}00Z.jsonl"
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
        _append_seal(
            logs_dir,
            segment_name=segment_name,
            seal_hash=seal_hash,
            first_hash=first_hash,
            last_hash=last_hash,
            line_count=line_count,
        )
        ok, _, error = append_segment_chain(
            runtime_root,
            segment_name=segment_name,
            seal_hash=seal_hash,
            line_count=line_count,
            last_hash=last_hash,
            segment_seq=index,
            prev_chain_hash=prev_chain_hash,
        )
        assert ok, error
        prev_chain_hash = json.loads((logs_dir / "segment_chain.jsonl").read_text(encoding="utf-8").splitlines()[-1])["chain_hash"]

    payload = build_ledger_root_payload(logs_dir, ts_utc="2026-03-07T01:00:00Z")
    write_ledger_root(logs_dir / "ledger_root.json", payload)
    return runtime_root


def _export_pack(tmp_path: Path) -> Path:
    runtime_root = _seed_runtime(tmp_path)
    out_dir = tmp_path / "export"
    export_proof_pack(runtime_root, out_dir, dry_run=False)
    return out_dir


def _run_report(export_dir: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "tools/ops/proof_report.py", "--path", str(export_dir), *extra],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_proof_pack_human_report_verified(tmp_path: Path) -> None:
    export_dir = _export_pack(tmp_path)

    result = _run_report(export_dir)

    assert result.returncode == 0
    assert "0luka Ledger Proof Verification" in result.stdout
    assert "VERIFIED" in result.stdout
    assert "checksums" in result.stdout
    assert "ledger_root" in result.stdout


def test_valid_proof_pack_json_ok_true(tmp_path: Path) -> None:
    export_dir = _export_pack(tmp_path)

    result = _run_report(export_dir, "--json")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["proof_pack"] == str(export_dir.resolve())
    assert payload["segment_seq_min"] == 1
    assert payload["segment_seq_max"] == 2
    assert payload["checks"]["ledger_root"]["ok"] is True


def test_tampered_checksum_fails_with_failed_output(tmp_path: Path) -> None:
    export_dir = _export_pack(tmp_path)
    checksums = export_dir / "checksums.sha256"
    checksums.write_text(checksums.read_text(encoding="utf-8").replace("  logs/", "  bogus/", 1), encoding="utf-8")

    result = _run_report(export_dir)

    assert result.returncode == 2
    assert "FAILED" in result.stdout
    assert "first_failure: checksums" in result.stdout


def test_missing_required_file_fails_cleanly(tmp_path: Path) -> None:
    export_dir = _export_pack(tmp_path)
    (export_dir / "logs" / "ledger_root.json").unlink()

    result = _run_report(export_dir, "--json")

    assert result.returncode == 3
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert payload["first_failure"] == "missing_required_file"
    assert payload["leaf_count"] is None


def test_stale_head_root_mismatch_fails_cleanly(tmp_path: Path) -> None:
    export_dir = _export_pack(tmp_path)
    ledger_root_path = export_dir / "logs" / "ledger_root.json"
    payload = json.loads(ledger_root_path.read_text(encoding="utf-8"))
    payload["segment_chain_head"] = _sha("stale-head")
    ledger_root_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

    result = _run_report(export_dir, "--json")

    assert result.returncode == 2
    verdict = json.loads(result.stdout)
    assert verdict["ok"] is False
    assert verdict["first_failure"] in {"checksums", "ledger_root"}


def test_deterministic_json_keys_and_shape(tmp_path: Path) -> None:
    export_dir = _export_pack(tmp_path)

    result = _run_report(export_dir, "--json")

    assert result.returncode == 0
    lines = result.stdout.strip().splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert list(payload.keys()) == [
        "ok",
        "proof_pack",
        "epoch_id",
        "leaf_count",
        "segment_seq_min",
        "segment_seq_max",
        "merkle_root",
        "checks",
        "first_failure",
        "errors",
    ]
