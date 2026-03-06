from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
REPO_ROOT = Path(__file__).resolve().parents[2]

from core.verify._test_root import ensure_test_root, restore_test_root_modules
from tools.ops.build_merkle_root import build_ledger_root_payload, write_ledger_root
from tools.ops.segment_chain_append import GENESIS_PREV_CHAIN_HASH, append_segment_chain


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _set_env(root: Path) -> dict[str, str | None]:
    old = {
        "ROOT": os.environ.get("ROOT"),
        "0LUKA_ROOT": os.environ.get("0LUKA_ROOT"),
        "LUKA_RUNTIME_ROOT": os.environ.get("LUKA_RUNTIME_ROOT"),
    }
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    os.environ.pop("LUKA_RUNTIME_ROOT", None)
    return old


def _restore_env(old: dict[str, str | None]) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


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


def _seed_runtime(root: Path) -> Path:
    ensure_test_root(root)
    runtime_root = root / "runtime"
    logs_dir = runtime_root / "logs"
    archive_dir = logs_dir / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)

    feed_line = _write_active_feed(logs_dir)
    _write_epoch_manifest(logs_dir, feed_line)

    prev_chain_hash = GENESIS_PREV_CHAIN_HASH
    for index in range(1, 3):
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
        prev_chain_hash = json.loads((logs_dir / "segment_chain.jsonl").read_text(encoding="utf-8").splitlines()[-1])[
            "chain_hash"
        ]

    payload = build_ledger_root_payload(logs_dir, ts_utc="2026-03-07T01:00:00Z")
    write_ledger_root(logs_dir / "ledger_root.json", payload)
    return runtime_root


def _run_cli(args: list[str], *, root: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ROOT"] = str(root)
    env["0LUKA_ROOT"] = str(root)
    env.pop("LUKA_RUNTIME_ROOT", None)
    return subprocess.run(
        [sys.executable, "-m", "core", *args],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )


def test_cli_ledger_verify_returns_ok_json() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            _seed_runtime(root)
            cp = _run_cli(["ledger", "verify"], root=root)
            assert cp.returncode == 0, cp.stderr or cp.stdout
            obj = json.loads(cp.stdout)
            assert obj["ok"] is True
            assert obj["checks"]["ledger_root"]["ok"] is True
        finally:
            restore_test_root_modules()
            _restore_env(old)


def test_cli_ledger_root_prints_current_root() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            runtime_root = _seed_runtime(root)
            payload = json.loads((runtime_root / "logs" / "ledger_root.json").read_text(encoding="utf-8"))
            cp = _run_cli(["ledger", "root"], root=root)
            assert cp.returncode == 0, cp.stderr or cp.stdout
            assert "Ledger Root" in cp.stdout
            assert payload["merkle_root"] in cp.stdout
        finally:
            restore_test_root_modules()
            _restore_env(old)
