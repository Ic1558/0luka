#!/usr/bin/env python3
"""Phase 5D regression tests for kernel retention."""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import time
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


def _load_retention(root: Path):
    mod = importlib.import_module("core.retention")
    mod = importlib.reload(mod)
    mod.ROOT = root
    return mod


def _read_activity_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        lines.append(json.loads(line))
    return lines


def test_log_rotation_triggers_on_size() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        log_dir = root / "observability" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "dispatcher.jsonl"
        log_path.write_text("x" * 2500, encoding="utf-8")

        retention = _load_retention(root)
        policy = {"path": "observability/logs/dispatcher.jsonl", "type": "log_rotate", "max_size_kb": 1, "keep_rotated": 3}
        result = retention.rotate_log(policy)
        assert result["rotated"] is True
        assert (log_dir / "dispatcher.jsonl.1").exists()
        assert log_path.exists()
        assert log_path.stat().st_size == 0

        log_path.write_text("y" * 2500, encoding="utf-8")
        result2 = retention.rotate_log(policy)
        assert result2["rotated"] is True
        assert (log_dir / "dispatcher.jsonl.2").exists()
        assert (log_dir / "dispatcher.jsonl.1").exists()

        print("test_log_rotation_triggers_on_size: ok")
        _restore_env(old)


def test_log_rotation_skips_small_file() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        log_dir = root / "observability" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "dispatcher.jsonl"
        log_path.write_text("tiny", encoding="utf-8")

        retention = _load_retention(root)
        policy = {"path": "observability/logs/dispatcher.jsonl", "type": "log_rotate", "max_size_kb": 100, "keep_rotated": 3}
        result = retention.rotate_log(policy)
        assert result["rotated"] is False
        assert not (log_dir / "dispatcher.jsonl.1").exists()

        print("test_log_rotation_skips_small_file: ok")
        _restore_env(old)


def test_dir_age_respects_keep_min() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        audit_dir = root / "observability" / "artifacts" / "router_audit"
        audit_dir.mkdir(parents=True, exist_ok=True)

        old_ts = time.time() - (40 * 86400)
        for idx in range(30):
            path = audit_dir / f"audit_{idx:02d}.json"
            path.write_text("{}", encoding="utf-8")
            os.utime(path, (old_ts, old_ts))

        retention = _load_retention(root)
        policy = {"path": "observability/artifacts/router_audit", "type": "dir_age", "max_age_days": 30, "keep_min": 10}
        result = retention.age_directory(policy)
        remaining = len([p for p in audit_dir.iterdir() if p.is_file()])
        assert result["deleted"] == 20
        assert remaining >= 10

        print("test_dir_age_respects_keep_min: ok")
        _restore_env(old)


def test_protected_paths_never_deleted() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        art_dir = root / "observability" / "artifacts"
        art_dir.mkdir(parents=True, exist_ok=True)

        protected = [
            art_dir / "dispatch_latest.json",
            art_dir / "dispatch_ledger.json",
            art_dir / "dispatcher_heartbeat.json",
        ]
        old_ts = time.time() - (100 * 86400)
        for p in protected:
            p.write_text("{}", encoding="utf-8")
            os.utime(p, (old_ts, old_ts))

        retention = _load_retention(root)
        policy = {
            "artifacts_age": {
                "path": "observability/artifacts",
                "type": "dir_age",
                "max_age_days": 1,
                "keep_min": 0,
            }
        }
        retention.run_retention(policy=policy)

        for p in protected:
            assert p.exists(), f"protected file removed: {p}"

        print("test_protected_paths_never_deleted: ok")
        _restore_env(old)


def test_dry_run_deletes_nothing() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        rej_dir = root / "interface" / "rejected"
        rej_dir.mkdir(parents=True, exist_ok=True)
        old_ts = time.time() - (20 * 86400)
        files = []
        for idx in range(5):
            p = rej_dir / f"r_{idx}.yaml"
            p.write_text("id: r\n", encoding="utf-8")
            os.utime(p, (old_ts, old_ts))
            files.append(p)

        retention = _load_retention(root)
        policy = {
            "rejected_tasks": {
                "path": "interface/rejected",
                "type": "dir_age",
                "max_age_days": 1,
                "keep_min": 0,
            }
        }
        summary = retention.run_retention(dry_run=True, policy=policy)
        for p in files:
            assert p.exists()
        assert summary["policies"]["rejected_tasks"]["would_delete"] == 5

        print("test_dry_run_deletes_nothing: ok")
        _restore_env(old)


def test_activity_feed_emits_important_events_no_hardpaths() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        (root / "observability" / "logs").mkdir(parents=True, exist_ok=True)
        (root / "observability" / "artifacts" / "router_audit").mkdir(parents=True, exist_ok=True)
        (root / "observability" / "artifacts").mkdir(parents=True, exist_ok=True)

        # rotation trigger
        log_path = root / "observability" / "logs" / "dispatcher.jsonl"
        log_path.write_text("z" * 2500, encoding="utf-8")

        # aged files for deletion
        old_ts = time.time() - (35 * 86400)
        audit_file = root / "observability" / "artifacts" / "router_audit" / "old_audit.json"
        audit_file.write_text("{}", encoding="utf-8")
        os.utime(audit_file, (old_ts, old_ts))

        # protected file in aged dir scope
        protected = root / "observability" / "artifacts" / "dispatch_latest.json"
        protected.write_text("{}", encoding="utf-8")
        os.utime(protected, (old_ts, old_ts))

        retention = _load_retention(root)
        policy = {
            "dispatcher_log": {
                "path": "observability/logs/dispatcher.jsonl",
                "type": "log_rotate",
                "max_size_kb": 1,
                "keep_rotated": 2,
            },
            "router_audit": {
                "path": "observability/artifacts/router_audit",
                "type": "dir_age",
                "max_age_days": 1,
                "keep_min": 0,
            },
            "artifacts_age": {
                "path": "observability/artifacts",
                "type": "dir_age",
                "max_age_days": 1,
                "keep_min": 0,
            },
        }
        retention.run_retention(policy=policy)

        activity_path = root / "observability" / "activity" / "activity.jsonl"
        events = _read_activity_lines(activity_path)
        types = [e.get("type") for e in events]
        assert "retention.rotate" in types
        assert "retention.delete" in types
        assert "retention.protected_skip" in types

        content = activity_path.read_text(encoding="utf-8")
        assert "/Users/" not in content
        assert "file:///Users" not in content

        print("test_activity_feed_emits_important_events_no_hardpaths: ok")
        _restore_env(old)


def main() -> int:
    test_log_rotation_triggers_on_size()
    test_log_rotation_skips_small_file()
    test_dir_age_respects_keep_min()
    test_protected_paths_never_deleted()
    test_dry_run_deletes_nothing()
    test_activity_feed_emits_important_events_no_hardpaths()
    print("test_retention: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
