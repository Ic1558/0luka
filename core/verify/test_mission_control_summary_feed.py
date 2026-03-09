#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib
import json
import os
import tempfile
from pathlib import Path


ROOT_REPO = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT_REPO))


def _set_env(root: Path) -> dict[str, str | None]:
    old = {
        "ROOT": os.environ.get("ROOT"),
    }
    os.environ["ROOT"] = str(root)
    return old


def _restore_env(old: dict[str, str | None]) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_mission_control_summary_consumes_feed_and_guard_truth_read_only() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            feed_path = root / "observability" / "logs" / "activity_feed.jsonl"
            violations_path = root / "observability" / "logs" / "feed_guard_violations.jsonl"
            proof_pack = root / "observability" / "artifacts" / "proof_packs" / "pack_001"
            proof_pack.mkdir(parents=True, exist_ok=True)
            (proof_pack / "linter.json").write_text('{"ok": true}\n', encoding="utf-8")

            _write_jsonl(
                feed_path,
                [
                    {"ts_utc": "2026-03-09T00:00:00Z", "action": "dispatch.start", "status_badge": "PROVEN"},
                    {"ts_utc": "2026-03-09T00:00:01Z", "action": "dispatch.end", "status_badge": "PROVEN"},
                ],
            )
            _write_jsonl(violations_path, [])

            module = importlib.reload(importlib.import_module("tools.mission_control"))
            module.ROOT = root
            module.FEED_PATH = feed_path
            module.VIOLATIONS_PATH = violations_path
            module.PROOF_PACKS_PATH = root / "observability" / "artifacts" / "proof_packs"
            module.INBOX_PATH = root / "interface" / "inbox"
            module.HEALTH_CACHE_PATH = root / "observability" / "artifacts" / "health_latest.json"
            module._run = lambda cmd: (0, "deadbeef", "") if cmd[:3] == ["git", "rev-parse", "HEAD"] else (1, "", "unavailable")

            before_hashes = {
                "feed": _sha(feed_path),
                "violations": _sha(violations_path),
            }

            summary = module.collect_summary(tail_n=10, packs_n=5, since_min=10_000_000, allow_inbox=False)

            assert summary["activity_feed"]["summary"]["count_in_window"] == 2
            assert summary["activity_feed"]["summary"]["by_action"]["dispatch.start"] == 1
            assert summary["guard_violations"]["summary"]["count_in_window"] == 0
            assert summary["runtime_health"] in {"DEGRADED", "UNKNOWN"}
            assert summary["system_health"]["violations"] == 0

            after_hashes = {
                "feed": _sha(feed_path),
                "violations": _sha(violations_path),
            }
            assert before_hashes == after_hashes
        finally:
            _restore_env(old)
