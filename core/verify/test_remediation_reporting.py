from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops import remediation_history_report


def _write_log(path: Path, entries: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


def test_empty_log_summary_valid(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))

    report = remediation_history_report.build_report([], lane=None, last=None)

    assert report["memory"]["attempts"] == 0
    assert report["worker"]["recovered"] == 0
    assert report["last_event"]["decision"] is None


def test_log_with_recovery_counts_correct(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    log_path = runtime_root / "state" / "remediation_actions.jsonl"
    _write_log(
        log_path,
        [
            {"timestamp": "2026-03-08T00:00:00Z", "decision": "approval_missing", "target": "memory", "reason": "memory_status=CRITICAL", "action_taken": False, "source": "remediation_engine"},
            {"timestamp": "2026-03-08T00:01:00Z", "decision": "cooldown_active", "target": "memory", "reason": "cooldown", "action_taken": False, "source": "remediation_engine"},
            {"timestamp": "2026-03-08T00:02:00Z", "decision": "remediation_escalated", "target": "memory", "reason": "max_attempts_exceeded", "action_taken": False, "source": "remediation_engine"},
            {"timestamp": "2026-03-08T00:03:00Z", "decision": "remediation_recovered", "target": "memory", "reason": "recovered", "action_taken": True, "source": "remediation_engine"},
        ],
    )
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))

    entries = remediation_history_report._read_entries(log_path)
    report = remediation_history_report.build_report(entries)

    assert report["memory"]["attempts"] == 3
    assert report["memory"]["cooldowns"] == 1
    assert report["memory"]["escalations"] == 1
    assert report["memory"]["recovered"] == 1


def test_lane_filter_works(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    log_path = runtime_root / "state" / "remediation_actions.jsonl"
    _write_log(
        log_path,
        [
            {"timestamp": "2026-03-08T00:00:00Z", "decision": "approval_missing", "target": "memory", "reason": "memory_status=CRITICAL", "action_taken": False, "source": "remediation_engine"},
            {"timestamp": "2026-03-08T00:01:00Z", "decision": "worker_recovery_started", "target": "worker", "reason": "bridge_status=FAILED", "action_taken": True, "source": "remediation_engine"},
        ],
    )
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))

    report = remediation_history_report.build_report(remediation_history_report._read_entries(log_path), lane="worker")

    assert "memory" not in report
    assert report["worker"]["attempts"] == 1


def test_json_output_valid(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    log_path = runtime_root / "state" / "remediation_actions.jsonl"
    _write_log(log_path, [])
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))

    proc = subprocess.run(
        [sys.executable, "tools/ops/remediation_history_report.py", "--json"],
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
        check=False,
    )

    payload = json.loads(proc.stdout)
    assert payload["memory"]["attempts"] == 0
    assert payload["total_entries"] == 0


def test_last_n_filtering_works(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    log_path = runtime_root / "state" / "remediation_actions.jsonl"
    _write_log(
        log_path,
        [
            {"timestamp": "2026-03-08T00:00:00Z", "decision": "approval_missing", "target": "memory", "reason": "a", "action_taken": False, "source": "remediation_engine"},
            {"timestamp": "2026-03-08T00:01:00Z", "decision": "approval_missing", "target": "memory", "reason": "b", "action_taken": False, "source": "remediation_engine"},
            {"timestamp": "2026-03-08T00:02:00Z", "decision": "noop", "target": "none", "reason": "c", "action_taken": False, "source": "remediation_engine"},
        ],
    )
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))

    report = remediation_history_report.build_report(remediation_history_report._read_entries(log_path), last=2)

    assert report["total_entries"] == 2
    assert report["memory"]["attempts"] == 1


def test_no_mutation_of_runtime_state(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    log_path = runtime_root / "state" / "remediation_actions.jsonl"
    _write_log(log_path, [])
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))

    remediation_history_report.build_report(remediation_history_report._read_entries(log_path))

    assert sorted(str(path.relative_to(runtime_root)) for path in runtime_root.rglob("*") if path.is_file()) == [
        "state/remediation_actions.jsonl"
    ]
