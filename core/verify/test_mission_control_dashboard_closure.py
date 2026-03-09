#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import os
import tempfile
from pathlib import Path

from starlette.testclient import TestClient


ROOT_REPO = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT_REPO))


def _set_env(root: Path) -> dict[str, str | None]:
    old = {
        "ROOT": os.environ.get("ROOT"),
        "LUKA_RUNTIME_ROOT": os.environ.get("LUKA_RUNTIME_ROOT"),
        "LUKA_OBSERVABILITY_ROOT": os.environ.get("LUKA_OBSERVABILITY_ROOT"),
    }
    os.environ["ROOT"] = str(root)
    os.environ["LUKA_RUNTIME_ROOT"] = str(root / "runtime_root")
    os.environ["LUKA_OBSERVABILITY_ROOT"] = str(root / "observability")
    return old


def _restore_env(old: dict[str, str | None]) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def test_root_dashboard_renders_system_activity_and_timelines_read_only() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            runtime_root = root / "runtime_root"
            observability_root = root / "observability"
            (runtime_root / "state").mkdir(parents=True, exist_ok=True)
            (observability_root / "logs").mkdir(parents=True, exist_ok=True)

            activity_path = observability_root / "logs" / "activity_feed.jsonl"
            activity_path.write_text(
                "\n".join(
                    [
                        json.dumps({"ts_utc": "2026-03-09T00:00:00Z", "action": "dispatch.start"}),
                        json.dumps({"ts_utc": "2026-03-09T00:00:01Z", "action": "guardian_recovery"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            before_hash = activity_path.read_text(encoding="utf-8")

            module = importlib.reload(importlib.import_module("interface.operator.mission_control_server"))
            client = TestClient(module.app)

            module.load_operator_status = lambda: {
                "ok": True,
                "overall_status": "HEALTHY",
                "memory_status": "OK",
                "api_server": "RUNNING",
                "redis": "RUNNING",
                "bridge_status": "OK",
            }
            module.load_runtime_status = lambda: {
                "ok": True,
                "system_health": {"status": "HEALTHY"},
                "proof_pack": {"epoch_id": "epoch-001"},
                "details": {"bridge_consumer": {"status": "idle", "inflight_count": 0, "outbox_count": 0}},
            }
            module.load_remediation_history = lambda lane=None, last=None: {
                "memory": {"attempts": 1, "cooldowns": 0, "escalations": 0, "recovered": 1, "lifecycle": ["memory_recovery_started", "memory_recovery_finished"]},
                "worker": {"attempts": 0, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": []},
                "timeline": [{"timestamp": None, "decision": "memory_recovery_finished", "lane": "memory"}],
                "last_event": {"decision": "memory_recovery_finished", "lane": "memory", "timestamp": "2026-03-09T00:00:02Z"},
                "total_entries": 1,
            }
            module.load_approval_history = lambda lane=None, last=None: {
                "events": [{"timestamp": "2026-03-09T00:00:03Z", "lane": "memory_recovery", "action": "approve", "actor": "Boss", "approved": True, "expires_at": None, "source": "approval_write"}],
                "last_event": {"timestamp": "2026-03-09T00:00:03Z", "lane": "memory_recovery", "action": "approve", "actor": "Boss", "approved": True, "expires_at": None, "source": "approval_write"},
                "total_entries": 1,
            }
            module.load_activity_entries = lambda limit=50: [
                {"ts_utc": "2026-03-09T00:00:00Z", "action": "dispatch.start"},
                {"ts_utc": "2026-03-09T00:00:01Z", "action": "guardian_recovery"},
            ]
            module.load_alerts = lambda limit=100: []
            module.load_autonomy_policy = lambda lane=None: {"lanes": {}}
            module.load_approval_presets = lambda: {"presets": []}
            module.load_approval_expiry = lambda: {"lanes": []}
            module.load_policy_drift = lambda: {"checks": {}}
            module.load_remediation_queue = lambda: {"items": []}
            module.load_remediation_audit_entries = lambda last=20: {"ok": True, "entries": []}
            module.load_approval_log_entries = lambda last=20: {"ok": True, "entries": []}
            module.load_runtime_decisions = lambda last=20: {"ok": True, "entries": []}

            response = client.get("/")
            assert response.status_code == 200
            body = response.text
            assert "Mission Control" in body
            assert "guardian_recovery" in body
            assert "memory_recovery_finished" in body
            assert "approve" in body
            assert "HEALTHY" in body
            assert activity_path.read_text(encoding="utf-8") == before_hash
        finally:
            _restore_env(old)


def test_remediation_and_approval_endpoints_return_timeline_shapes() -> None:
    module = importlib.reload(importlib.import_module("interface.operator.mission_control_server"))
    client = TestClient(module.app)

    module.load_remediation_audit_entries = lambda last=100: {"ok": True, "entries": [{"timestamp": "2026-03-09T00:00:00Z", "decision": "memory_recovery_started"}]}
    module.load_remediation_history = lambda lane=None, last=None: {
        "memory": {"attempts": 1, "cooldowns": 0, "escalations": 0, "recovered": 1, "lifecycle": ["memory_recovery_started"]},
        "worker": {"attempts": 0, "cooldowns": 0, "escalations": 0, "recovered": 0, "lifecycle": []},
        "timeline": [{"timestamp": None, "decision": "memory_recovery_started", "lane": "memory"}],
        "last_event": {"decision": "memory_recovery_started", "lane": "memory", "timestamp": None},
        "total_entries": 1,
    }
    module.load_approval_history = lambda lane=None, last=None: {
        "events": [{"timestamp": "2026-03-09T00:00:03Z", "lane": "memory_recovery", "action": "approve", "actor": "Boss", "approved": True, "expires_at": None, "source": "approval_write"}],
        "last_event": {"timestamp": "2026-03-09T00:00:03Z", "lane": "memory_recovery", "action": "approve", "actor": "Boss", "approved": True, "expires_at": None, "source": "approval_write"},
        "total_entries": 1,
    }

    remediation = client.get("/api/remediation_history?last=10")
    approval = client.get("/api/approval_history?last=10")

    assert remediation.status_code == 200
    remediation_payload = remediation.json()
    assert "timeline" in remediation_payload
    assert remediation_payload["timeline"][0]["lane"] == "memory"

    assert approval.status_code == 200
    approval_payload = approval.json()
    assert approval_payload["events"][0]["lane"] == "memory_recovery"
