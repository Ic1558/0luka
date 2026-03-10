from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ops import memory_recovery, remediation_engine


def _cp(args: list[str], rc: int, payload: dict[str, object]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=rc, stdout=json.dumps(payload), stderr="")


def test_healthy_non_critical_memory_noop() -> None:
    decisions = memory_recovery.evaluate_memory_recovery(
        {"overall_status": "HEALTHY"},
        {"overall_status": "HEALTHY", "memory_status": "OK"},
        timestamp="2026-03-08T00:00:00Z",
    )

    assert len(decisions) == 1
    assert decisions[0]["decision"] == "noop"
    assert decisions[0]["target"] == "none"


def test_memory_critical_no_approval() -> None:
    decisions = memory_recovery.evaluate_memory_recovery(
        {"overall_status": "HEALTHY"},
        {"overall_status": "DEGRADED", "memory_status": "CRITICAL"},
        timestamp="2026-03-08T00:00:00Z",
    )

    assert decisions[0]["decision"] == "approval_missing"
    assert decisions[0]["target"] == "memory"


def test_memory_critical_no_safe_recovery_path(monkeypatch) -> None:
    monkeypatch.setenv("LUKA_ALLOW_MEMORY_RECOVERY", "1")

    decisions = memory_recovery.evaluate_memory_recovery(
        {"overall_status": "HEALTHY"},
        {"overall_status": "DEGRADED", "memory_status": "CRITICAL"},
        timestamp="2026-03-08T00:00:00Z",
        runtime_root=Path("/nonexistent/runtime"),
    )

    assert decisions[0]["decision"] == "action_unavailable"
    assert decisions[0]["target"] == "memory"


def test_approved_memory_recovery_path_action_taken(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LUKA_ALLOW_MEMORY_RECOVERY", "1")
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "policy_memory.json").write_text(
        json.dumps(
            {
                "updated_at": "2026-03-07T00:00:00Z",
                "protected_domains": [{"domain": "x.example"}],
                "outcomes": [{"status": 200}],
            }
        ),
        encoding="utf-8",
    )

    decisions = memory_recovery.evaluate_memory_recovery(
        {"overall_status": "HEALTHY"},
        {"overall_status": "DEGRADED", "memory_status": "CRITICAL"},
        timestamp="2026-03-08T00:00:00Z",
        runtime_root=runtime_root,
    )

    assert [item["decision"] for item in decisions] == ["memory_recovery_started", "memory_recovery_finished"]
    assert all(item["action_taken"] is True for item in decisions)
    metadata = json.loads((state_dir / "memory_index_metadata.json").read_text(encoding="utf-8"))
    assert metadata["protected_domain_count"] == 1
    assert metadata["outcome_count"] == 1


def test_remediation_log_schema_valid_and_scoped(tmp_path: Path, monkeypatch) -> None:
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "policy_memory.json").write_text(
        json.dumps({"updated_at": "2026-03-07T00:00:00Z", "protected_domains": [], "outcomes": []}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LUKA_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setattr(memory_recovery, "_utc_now", lambda: "2026-03-08T00:00:00Z")

    def fake_run(args, cwd, capture_output, text, env, check):
        cmd = args[1:]
        if cmd == ["tools/ops/runtime_status_report.py", "--json"]:
            return _cp(args, 0, {"overall_status": "HEALTHY"})
        if cmd == ["tools/ops/operator_status_report.py", "--json"]:
            return _cp(args, 0, {"overall_status": "HEALTHY", "memory_status": "OK"})
        raise AssertionError(args)

    monkeypatch.setattr(subprocess, "run", fake_run)

    decisions = memory_recovery.run_once(runtime_root=runtime_root)

    assert decisions[0]["timestamp"] == "2026-03-08T00:00:00Z"
    lines = (runtime_root / "state" / "remediation_actions.jsonl").read_text(encoding="utf-8").splitlines()
    stored = json.loads(lines[0])
    assert list(stored.keys()) == ["timestamp", "decision", "target", "reason", "action_taken", "source"]
    assert stored["source"] == "remediation_engine"
    assert sorted(str(path.relative_to(runtime_root)) for path in runtime_root.rglob("*") if path.is_file()) == [
        "state/policy_memory.json",
        "state/remediation_actions.jsonl"
    ]


def test_remediation_engine_emits_memory_recovery_path(monkeypatch) -> None:
    monkeypatch.setattr(
        memory_recovery,
        "evaluate_memory_recovery",
        lambda runtime_status, operator_status, timestamp=None: [
            {
                "timestamp": "2026-03-08T00:00:00Z",
                "decision": "approval_missing",
                "target": "memory",
                "reason": "memory_status=CRITICAL; approval_missing:LUKA_ALLOW_MEMORY_RECOVERY",
                "action_taken": False,
                "source": "remediation_engine",
            }
        ],
    )

    decisions = remediation_engine.evaluate_remediation(
        {"overall_status": "HEALTHY"},
        {"overall_status": "DEGRADED", "api_server": "RUNNING", "redis": "RUNNING", "memory_status": "CRITICAL"},
        timestamp="2026-03-08T00:00:00Z",
    )

    assert decisions[0]["decision"] == "approval_missing"
    assert decisions[0]["target"] == "memory"
