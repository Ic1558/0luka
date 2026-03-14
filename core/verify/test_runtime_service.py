from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime.runtime_service import RuntimeService, resolve_runtime_root


def _write_schema(root: Path) -> None:
    schema_path = root / "interface" / "schemas" / "task_spec_v2.yaml"
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(
        "\n".join(
            [
                "version: 2",
                "required:",
                "  - task_id",
                "  - author",
                "  - intent",
                "  - operations",
                "rules:",
                "  lane:",
                "    allowed: [\"task\", \"lisa\", \"cole\", \"paula\"]",
                "  executor:",
                "    allowed: [\"shell\", \"lisa\", \"cole\", \"paula\"]",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_resolve_runtime_root_from_explicit_arg(tmp_path: Path) -> None:
    resolved = resolve_runtime_root(tmp_path)
    assert resolved == tmp_path.resolve()


def test_validate_boundary_supports_bridge_v1_compat(tmp_path: Path) -> None:
    _write_schema(tmp_path)
    service = RuntimeService.create(runtime_root=tmp_path, service_name="bridge")
    legacy_task = {
        "task_id": "t1",
        "intent": "lisa.exec_shell",
        "executor": "lisa",
        "payload": {"command": "echo hi"},
    }
    ok, normalized, errors = service.validate_task_boundary(legacy_task, allow_compat_v1=True)
    assert ok is True
    assert errors == []
    assert normalized["lane"] == "lisa"
    assert isinstance(normalized["operations"], list)
    assert normalized["operations"][0]["tool"] == "lisa"


def test_validate_boundary_rejects_lane_mismatch(tmp_path: Path) -> None:
    _write_schema(tmp_path)
    service = RuntimeService.create(runtime_root=tmp_path, service_name="bridge")
    task = {
        "version": 2,
        "task_id": "t2",
        "created_at_utc": "2026-03-14T00:00:00Z",
        "author": "human",
        "intent": "cole.search_docs",
        "lane": "task",
        "executor": "cole",
        "operations": [{"id": "t2:op1", "tool": "cole", "params": {"query": "q"}}],
        "payload": {"query": "q"},
    }
    ok, _, errors = service.validate_task_boundary(task, allow_compat_v1=True)
    assert ok is False
    assert "invalid:lane_intent_mismatch" in errors


def test_record_transition_writes_system_ledger(tmp_path: Path) -> None:
    _write_schema(tmp_path)
    service = RuntimeService.create(runtime_root=tmp_path, service_name="dispatcher")
    service.record_transition(
        task_id="t3",
        phase="dispatcher.start",
        status="started",
        detail="test",
    )
    ledger_path = tmp_path / "observability" / "stl" / "ledger" / "global_beacon.jsonl"
    assert ledger_path.exists()
    rows = [line for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(rows) == 1
    event = json.loads(rows[0])
    assert event["task_id"] == "t3"
    assert event["service"] == "dispatcher"
    assert event["phase"] == "dispatcher.start"
