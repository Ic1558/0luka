from __future__ import annotations

import json
import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server
from tools.ops import control_plane_execution_bridge
from tools.ops.control_plane_persistence import make_decision_id


def test_health_endpoint_returns_ok() -> None:
    client = TestClient(mission_control_server.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_operator_status_endpoint_returns_json(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(mission_control_server, "load_operator_status", lambda: {"ok": True, "overall_status": "CRITICAL"})

    response = client.get("/api/operator_status")

    assert response.status_code == 200
    assert response.json()["overall_status"] == "CRITICAL"


def test_runtime_status_endpoint_returns_json(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_runtime_status",
        lambda: {"ok": True, "system_health": {"status": "HEALTHY"}, "proof_pack": {"epoch_id": 64}},
    )

    response = client.get("/api/runtime_status")

    assert response.status_code == 200
    assert response.json()["system_health"]["status"] == "HEALTHY"


def test_activity_endpoint_returns_list(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_activity_entries",
        lambda limit=50: [{"ts_utc": "2026-03-08T00:00:00Z", "action": "proof_export"}],
    )

    response = client.get("/api/activity")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert response.json()[0]["action"] == "proof_export"


def test_proof_artifacts_endpoint_returns_inventory(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_proof_artifacts",
        lambda limit=50: {
            "artifacts": [
                {
                    "artifact_type": "proof_pack",
                    "name": "pack_001",
                    "path": "/tmp/proof_packs/pack_001",
                    "manifest_present": True,
                    "mtime_utc": 1741392000.0,
                }
            ],
            "total_entries": 1,
        },
    )

    response = client.get("/api/proof_artifacts?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_entries"] == 1
    assert payload["artifacts"][0]["artifact_type"] == "proof_pack"
    assert payload["artifacts"][0]["manifest_present"] is True


def test_proof_artifact_detail_endpoint_returns_json(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    proof_root = tmp_path / "observability" / "artifacts" / "proof_packs"
    export_root = tmp_path / "runtime" / "exports"
    artifact_dir = proof_root / "pack_001"
    artifact_dir.mkdir(parents=True)
    export_root.mkdir(parents=True)
    note = artifact_dir / "summary.json"
    note.write_text('{"ok": true}', encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: tmp_path / "observability")
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: tmp_path / "runtime")

    before = note.read_text(encoding="utf-8")
    response = client.get("/api/proof_artifacts/proof_pack:pack_001")

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_id"] == "proof_pack:pack_001"
    assert payload["artifact_type"] == "proof_pack"
    assert payload["exists"] is True
    assert payload["entries"][0]["name"] == "summary.json"
    assert note.read_text(encoding="utf-8") == before


def test_proof_artifact_detail_endpoint_returns_404_for_missing(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    (tmp_path / "observability" / "artifacts" / "proof_packs").mkdir(parents=True)
    (tmp_path / "runtime" / "exports").mkdir(parents=True)

    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: tmp_path / "observability")
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: tmp_path / "runtime")

    response = client.get("/api/proof_artifacts/proof_pack:missing_pack")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_proof_artifact_detail_endpoint_rejects_traversal(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    (tmp_path / "observability" / "artifacts" / "proof_packs").mkdir(parents=True)
    (tmp_path / "runtime" / "exports").mkdir(parents=True)

    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: tmp_path / "observability")
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: tmp_path / "runtime")

    response = client.get("/api/proof_artifacts/proof_pack:..")

    assert response.status_code == 400
    assert response.json()["error"] == "unsafe_artifact_id"


def test_qs_runs_endpoint_returns_list(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_qs_runs",
        lambda limit=100: {"ok": True, "runs": [{"run_id": "qs_run_1"}], "total_entries": 1},
    )

    response = client.get("/api/qs_runs")

    assert response.status_code == 200
    assert response.json()["runs"][0]["run_id"] == "qs_run_1"


def test_qs_runs_endpoint_safe_empty(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_qs_runs",
        lambda limit=100: {"ok": True, "runs": [], "total_entries": 0},
    )

    response = client.get("/api/qs_runs")

    assert response.status_code == 200
    assert response.json()["runs"] == []


def test_qs_runs_endpoint_returns_proof_artifacts(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    qs_runs_dir = runtime_root / "state" / "qs_runs"
    proof_pack_dir = observability_root / "artifacts" / "proof_packs" / "run_123"
    export_dir = runtime_root / "exports" / "run_123"
    qs_runs_dir.mkdir(parents=True)
    proof_pack_dir.mkdir(parents=True)
    export_dir.mkdir(parents=True)
    (qs_runs_dir / "run_123.json").write_text('{"run_id": "run_123", "status": "completed"}', encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/qs_runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runs"][0]["proof_artifacts"] == [
        "proof_pack:run_123",
        "ledger_proof_export:run_123",
    ]
    assert payload["runs"][0]["artifact_count"] == 2
    assert payload["runs"][0]["missing_artifacts"] == []
    assert payload["runs"][0]["signal"] == "COMPLETE"


def test_qs_runs_endpoint_returns_empty_artifacts_when_missing(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    qs_runs_dir = runtime_root / "state" / "qs_runs"
    qs_runs_dir.mkdir(parents=True)
    (runtime_root / "exports").mkdir(parents=True)
    (observability_root / "artifacts" / "proof_packs").mkdir(parents=True)
    (qs_runs_dir / "run_456.json").write_text('{"run_id": "run_456", "status": "completed"}', encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/qs_runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["runs"][0]["proof_artifacts"] == []
    assert payload["runs"][0]["artifact_count"] == 0
    assert payload["runs"][0]["missing_artifacts"] == [
        "proof_pack:run_456",
        "ledger_proof_export:run_456",
    ]
    assert payload["runs"][0]["signal"] == "MISSING_PROOF"


def test_qs_run_detail_endpoint_returns_json(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_qs_run",
        lambda run_id: {"run_id": run_id, "status": "completed"} if run_id == "valid_id" else None,
    )

    response = client.get("/api/qs_runs/valid_id")

    assert response.status_code == 200
    assert response.json()["run_id"] == "valid_id"


def test_qs_run_detail_endpoint_includes_interpretation(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    qs_runs_dir = runtime_root / "state" / "qs_runs"
    proof_pack_dir = observability_root / "artifacts" / "proof_packs" / "run_789"
    qs_runs_dir.mkdir(parents=True)
    proof_pack_dir.mkdir(parents=True)
    (runtime_root / "exports").mkdir(parents=True)
    (qs_runs_dir / "run_789.json").write_text('{"run_id": "run_789", "status": "completed"}', encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/qs_runs/run_789")

    assert response.status_code == 200
    payload = response.json()
    assert payload["proof_artifacts"] == ["proof_pack:run_789"]
    assert payload["artifact_count"] == 1
    assert payload["missing_artifacts"] == ["ledger_proof_export:run_789"]
    assert payload["signal"] == "PARTIAL"


def test_qs_run_detail_endpoint_rejects_traversal(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    qs_runs_dir = runtime_root / "state" / "qs_runs"
    qs_runs_dir.mkdir(parents=True)
    (runtime_root / "exports").mkdir(parents=True)
    (observability_root / "artifacts" / "proof_packs").mkdir(parents=True)
    (qs_runs_dir / "..json").write_text('{"run_id": "..", "status": "completed"}', encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/qs_runs/%2E%2E")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_qs_run_detail_endpoint_returns_404(monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    monkeypatch.setattr(
        mission_control_server,
        "load_qs_run",
        lambda run_id: None,
    )

    response = client.get("/api/qs_runs/invalid_id")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_qs_run_artifacts_endpoint_returns_artifacts(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    qs_runs_dir = runtime_root / "state" / "qs_runs"
    proof_pack_dir = observability_root / "artifacts" / "proof_packs" / "run_123"
    export_dir = runtime_root / "exports" / "run_123"
    qs_runs_dir.mkdir(parents=True)
    proof_pack_dir.mkdir(parents=True)
    export_dir.mkdir(parents=True)
    (qs_runs_dir / "run_123.json").write_text('{"run_id": "run_123", "status": "completed"}', encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/qs_runs/run_123/artifacts")

    assert response.status_code == 200
    assert response.json() == {
        "run_id": "run_123",
        "artifacts": [
            {"artifact_id": "proof_pack:run_123", "artifact_type": "proof_pack", "exists": True},
            {"artifact_id": "ledger_proof_export:run_123", "artifact_type": "ledger_proof_export", "exists": True},
        ],
    }


def test_qs_run_artifacts_endpoint_handles_missing_artifacts(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    qs_runs_dir = runtime_root / "state" / "qs_runs"
    qs_runs_dir.mkdir(parents=True)
    (runtime_root / "exports").mkdir(parents=True)
    (observability_root / "artifacts" / "proof_packs").mkdir(parents=True)
    (qs_runs_dir / "run_456.json").write_text('{"run_id": "run_456", "status": "completed"}', encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/qs_runs/run_456/artifacts")

    assert response.status_code == 200
    assert response.json() == {
        "run_id": "run_456",
        "artifacts": [
            {"artifact_id": "proof_pack:run_456", "artifact_type": "proof_pack", "exists": False},
            {"artifact_id": "ledger_proof_export:run_456", "artifact_type": "ledger_proof_export", "exists": False},
        ],
    }


def test_qs_run_artifacts_endpoint_rejects_unsafe_run_id(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    qs_runs_dir = runtime_root / "state" / "qs_runs"
    qs_runs_dir.mkdir(parents=True)
    (runtime_root / "exports").mkdir(parents=True)
    (observability_root / "artifacts" / "proof_packs").mkdir(parents=True)

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/qs_runs/%2E%2E/artifacts")

    assert response.status_code == 404
    assert response.json()["error"] == "not_found"


def test_system_model_endpoint_returns_json_when_file_exists(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    model_path = state_dir / "system_model.json"
    model_path.write_text(
        '{"current_phase":"I","eligibility_to_act":false,"repos_qs_boundary":"frozen_canonical","decision_memory_present":true}',
        encoding="utf-8",
    )

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)

    response = client.get("/api/system_model")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "system_model": {
            "current_phase": "I",
            "eligibility_to_act": False,
            "repos_qs_boundary": "frozen_canonical",
            "decision_memory_present": True,
        },
    }


def test_system_model_endpoint_returns_404_when_missing(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    (runtime_root / "state").mkdir(parents=True)

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)

    response = client.get("/api/system_model")

    assert response.status_code == 404
    assert response.json() == {"ok": False, "error": "system_model_not_found"}


def test_system_model_endpoint_returns_500_when_malformed(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "system_model.json").write_text("{not-json", encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)

    response = client.get("/api/system_model")

    assert response.status_code == 500
    assert response.json() == {"ok": False, "error": "system_model_unreadable"}


def test_system_model_endpoint_is_read_only_and_creates_no_files(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    model_path = state_dir / "system_model.json"
    model_path.write_text('{"current_phase":"I"}', encoding="utf-8")
    before = model_path.read_text(encoding="utf-8")
    before_files = sorted(path.relative_to(runtime_root).as_posix() for path in runtime_root.rglob("*"))

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)

    response = client.get("/api/system_model")

    after_files = sorted(path.relative_to(runtime_root).as_posix() for path in runtime_root.rglob("*"))
    assert response.status_code == 200
    assert model_path.read_text(encoding="utf-8") == before
    assert after_files == before_files


def test_system_model_endpoint_has_no_repos_qs_dependency(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "system_model.json").write_text('{"repos_qs_boundary":"frozen_canonical"}', encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(
        mission_control_server,
        "_observability_root",
        lambda: (_ for _ in ()).throw(AssertionError("observability root should not be used")),
    )

    response = client.get("/api/system_model")

    assert response.status_code == 200
    assert response.json()["system_model"]["repos_qs_boundary"] == "frozen_canonical"


def test_system_model_endpoint_wrapper_introduces_no_control_plane_fields(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    (state_dir / "system_model.json").write_text('{"control_plane_enabled":false,"autonomy_enabled":false}', encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)

    response = client.get("/api/system_model")

    assert response.status_code == 200
    assert set(response.json()) == {"ok", "system_model"}
    assert "action" not in response.json()
    assert "queue" not in response.json()
    assert "remediation" not in response.json()


def test_decisions_latest_returns_pending_structure_when_pending_exists(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    decision_id = make_decision_id(
        trace_id="trace-123",
        ts_utc="2026-03-11T12:00:00Z",
        signal_received="MISSING_PROOF",
        proposed_action="REVIEW_PROOF",
    )
    (state_dir / "decision_latest.json").write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace-123",
                "signal_received": "MISSING_PROOF",
                "proposed_action": "REVIEW_PROOF",
                "evidence_refs": ["proof_pack:run_123"],
                "ts_utc": "2026-03-11T12:00:00Z",
                "operator_status": "PENDING",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    assert response.json() == {
        "pending": {
            "decision_id": decision_id,
            "trace_id": "trace-123",
            "signal_received": "MISSING_PROOF",
            "proposed_action": "REVIEW_PROOF",
            "evidence_refs": ["proof_pack:run_123"],
            "ts_utc": "2026-03-11T12:00:00Z",
            "operator_status": "PENDING",
            "operator_note": None,
            "execution": None,
        },
        "latest": {
            "decision_id": decision_id,
            "trace_id": "trace-123",
            "signal_received": "MISSING_PROOF",
            "proposed_action": "REVIEW_PROOF",
            "evidence_refs": ["proof_pack:run_123"],
            "ts_utc": "2026-03-11T12:00:00Z",
            "operator_status": "PENDING",
            "operator_note": None,
            "execution": None,
        },
    }


def test_post_decisions_latest_approve_resolves_pending_decision(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    decision_id = make_decision_id(
        trace_id="trace-approve",
        ts_utc="2026-03-11T12:10:00Z",
        signal_received="UNKNOWN",
        proposed_action="ESCALATE",
    )
    latest_path = state_dir / "decision_latest.json"
    latest_path.write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace-approve",
                "signal_received": "UNKNOWN",
                "proposed_action": "ESCALATE",
                "evidence_refs": ["proof_pack:run_approve"],
                "ts_utc": "2026-03-11T12:10:00Z",
                "operator_status": "PENDING",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.post("/api/decisions/latest/approve", json={"operator_note": "looks valid"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["decision"]["operator_status"] == "APPROVED"
    assert payload["decision"]["operator_note"] == "looks valid"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    assert latest["operator_status"] == "APPROVED"
    rows = [
        json.loads(line)
        for line in (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["event"] == "OPERATOR_APPROVED"
    assert rows[-1]["decision_id"] == decision_id


def test_post_decisions_latest_reject_resolves_pending_decision(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    decision_id = make_decision_id(
        trace_id="trace-reject",
        ts_utc="2026-03-11T12:11:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    latest_path = state_dir / "decision_latest.json"
    latest_path.write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace-reject",
                "signal_received": "INCONSISTENT",
                "proposed_action": "QUARANTINE",
                "evidence_refs": ["proof_pack:run_reject"],
                "ts_utc": "2026-03-11T12:11:00Z",
                "operator_status": "PENDING",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.post("/api/decisions/latest/reject", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["decision"]["operator_status"] == "REJECTED"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    assert latest["operator_status"] == "REJECTED"
    rows = [
        json.loads(line)
        for line in (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["event"] == "OPERATOR_REJECTED"
    assert rows[-1]["decision_id"] == decision_id


def test_approve_fails_safely_when_no_pending_decision_exists(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    (runtime_root / "state").mkdir(parents=True)

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.post("/api/decisions/latest/approve", json={})

    assert response.status_code == 409
    assert response.json() == {"ok": False, "error": "no_pending_decision"}
    assert not (observability_root / "logs" / "decision_log.jsonl").exists()


def test_reject_fails_safely_when_latest_decision_is_not_pending(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    decision_id = make_decision_id(
        trace_id="trace-done",
        ts_utc="2026-03-11T12:12:00Z",
        signal_received="UNKNOWN",
        proposed_action="ESCALATE",
    )
    latest_path = state_dir / "decision_latest.json"
    latest_path.write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace-done",
                "signal_received": "UNKNOWN",
                "proposed_action": "ESCALATE",
                "evidence_refs": ["proof_pack:run_done"],
                "ts_utc": "2026-03-11T12:12:00Z",
                "operator_status": "APPROVED",
                "operator_note": "already handled",
            }
        ),
        encoding="utf-8",
    )
    before = latest_path.read_text(encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.post("/api/decisions/latest/reject", json={})

    assert response.status_code == 409
    assert response.json() == {"ok": False, "error": "decision_not_pending"}
    assert latest_path.read_text(encoding="utf-8") == before
    assert not (observability_root / "logs" / "decision_log.jsonl").exists()


def test_operator_note_is_recorded_when_provided(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    decision_id = make_decision_id(
        trace_id="trace-note",
        ts_utc="2026-03-11T12:13:00Z",
        signal_received="MISSING_PROOF",
        proposed_action="REVIEW_PROOF",
    )
    latest_path = state_dir / "decision_latest.json"
    latest_path.write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace-note",
                "signal_received": "MISSING_PROOF",
                "proposed_action": "REVIEW_PROOF",
                "evidence_refs": ["proof_pack:run_note"],
                "ts_utc": "2026-03-11T12:13:00Z",
                "operator_status": "PENDING",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.post("/api/decisions/latest/reject", json={"operator_note": "missing proof remains"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"]["operator_note"] == "missing proof remains"
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    assert latest["operator_note"] == "missing proof remains"


def test_resolution_endpoints_do_not_call_execution_hooks(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    decision_id = make_decision_id(
        trace_id="trace-safe",
        ts_utc="2026-03-11T12:14:00Z",
        signal_received="UNKNOWN",
        proposed_action="ESCALATE",
    )
    latest_path = state_dir / "decision_latest.json"
    latest_path.write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace-safe",
                "signal_received": "UNKNOWN",
                "proposed_action": "ESCALATE",
                "evidence_refs": ["proof_pack:run_safe"],
                "ts_utc": "2026-03-11T12:14:00Z",
                "operator_status": "PENDING",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(mission_control_server, "enqueue_remediation_queue", lambda **_: (_ for _ in ()).throw(AssertionError("no remediation queue")))
    monkeypatch.setattr(mission_control_server, "apply_approval_action", lambda **_: (_ for _ in ()).throw(AssertionError("no approval flow")))

    response = client.post("/api/decisions/latest/approve", json={})

    assert response.status_code == 200


def test_decisions_history_endpoint_returns_ledger_events(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    observability_root = tmp_path / "observability"
    log_dir = observability_root / "logs"
    log_dir.mkdir(parents=True)
    ledger_path = log_dir / "decision_log.jsonl"
    ledger_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event": "PROPOSAL_CREATED",
                        "decision_id": "decision_1",
                        "trace_id": "trace_1",
                        "ts_utc": "2026-03-11T12:20:00Z",
                        "operator_status": "PENDING",
                        "proposed_action": "REVIEW_PROOF",
                        "evidence_refs": ["proof_pack:run_1"],
                    }
                ),
                json.dumps(
                    {
                        "event": "OPERATOR_REJECTED",
                        "decision_id": "decision_1",
                        "trace_id": "trace_1",
                        "ts_utc": "2026-03-11T12:21:00Z",
                        "operator_status": "REJECTED",
                        "proposed_action": "REVIEW_PROOF",
                        "evidence_refs": ["proof_pack:run_1"],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/history")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["items"][0]["event_type"] == "PROPOSED"
    assert payload["items"][1]["event_type"] == "OPERATOR_REJECTED"
    assert payload["items"][0]["trace_id"] == "trace_1"


def test_decisions_history_endpoint_is_read_only(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    observability_root = tmp_path / "observability"
    log_dir = observability_root / "logs"
    log_dir.mkdir(parents=True)
    ledger_path = log_dir / "decision_log.jsonl"
    original = json.dumps(
        {
            "event": "PROPOSAL_CREATED",
            "decision_id": "decision_ro",
            "trace_id": "trace_ro",
            "ts_utc": "2026-03-11T12:22:00Z",
            "operator_status": "PENDING",
            "proposed_action": "ESCALATE",
            "evidence_refs": ["proof_pack:run_ro"],
        }
    ) + "\n"
    ledger_path.write_text(original, encoding="utf-8")
    before = ledger_path.read_text(encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/history?limit=5")

    assert response.status_code == 200
    assert ledger_path.read_text(encoding="utf-8") == before


def test_decisions_latest_endpoint_returns_pending_only_current_state(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    latest_path = state_dir / "decision_latest.json"
    decision_id = make_decision_id(
        trace_id="trace_latest",
        ts_utc="2026-03-11T12:23:00Z",
        signal_received="UNKNOWN",
        proposed_action="ESCALATE",
    )
    latest_path.write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace_latest",
                "signal_received": "UNKNOWN",
                "proposed_action": "ESCALATE",
                "evidence_refs": ["proof_pack:run_latest"],
                "ts_utc": "2026-03-11T12:23:00Z",
                "operator_status": "APPROVED",
                "operator_note": "reviewed",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    assert response.json() == {
        "pending": None,
        "latest": {
            "decision_id": decision_id,
            "trace_id": "trace_latest",
            "signal_received": "UNKNOWN",
            "proposed_action": "ESCALATE",
            "evidence_refs": ["proof_pack:run_latest"],
            "ts_utc": "2026-03-11T12:23:00Z",
            "operator_status": "APPROVED",
            "operator_note": "reviewed",
            "execution": None,
        },
    }


def test_decisions_history_endpoint_returns_events_in_ledger_order(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    observability_root = tmp_path / "observability"
    log_dir = observability_root / "logs"
    log_dir.mkdir(parents=True)
    ledger_path = log_dir / "decision_log.jsonl"
    rows = [
        {
            "event": "PROPOSAL_CREATED",
            "decision_id": "decision_1",
            "trace_id": "trace_1",
            "ts_utc": "2026-03-11T12:24:00Z",
            "operator_status": "PENDING",
            "proposed_action": "REVIEW_PROOF",
            "evidence_refs": ["proof_pack:run_1"],
        },
        {
            "event": "OPERATOR_APPROVED",
            "decision_id": "decision_1",
            "trace_id": "trace_1",
            "ts_utc": "2026-03-11T12:25:00Z",
            "operator_status": "APPROVED",
            "proposed_action": "REVIEW_PROOF",
            "evidence_refs": ["proof_pack:run_1"],
        },
        {
            "event": "PROPOSAL_CREATED",
            "decision_id": "decision_2",
            "trace_id": "trace_2",
            "ts_utc": "2026-03-11T12:26:00Z",
            "operator_status": "PENDING",
            "proposed_action": "QUARANTINE",
            "evidence_refs": ["proof_pack:run_2"],
        },
    ]
    ledger_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/history?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert [item["decision_id"] for item in payload["items"]] == ["decision_1", "decision_1", "decision_2"]
    assert [item["event_type"] for item in payload["items"]] == ["PROPOSED", "OPERATOR_APPROVED", "PROPOSED"]


def test_decisions_history_endpoint_enforces_limit(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    observability_root = tmp_path / "observability"
    log_dir = observability_root / "logs"
    log_dir.mkdir(parents=True)
    ledger_path = log_dir / "decision_log.jsonl"
    rows = []
    for idx in range(4):
        rows.append(
            {
                "event": "PROPOSAL_CREATED",
                "decision_id": f"decision_{idx}",
                "trace_id": f"trace_{idx}",
                "ts_utc": f"2026-03-11T12:2{idx}:00Z",
                "operator_status": "PENDING",
                "proposed_action": "ESCALATE",
                "evidence_refs": [f"proof_pack:run_{idx}"],
            }
        )
    ledger_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/history?limit=2")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert [item["decision_id"] for item in payload["items"]] == ["decision_2", "decision_3"]


def test_decisions_history_endpoint_does_not_mutate_runtime_or_ledger(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    state_dir = runtime_root / "state"
    log_dir = observability_root / "logs"
    state_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    latest_path = state_dir / "decision_latest.json"
    latest_path.write_text(
        json.dumps(
            {
                "decision_id": "decision_safe",
                "trace_id": "trace_safe",
                "signal_received": "UNKNOWN",
                "proposed_action": "ESCALATE",
                "evidence_refs": ["proof_pack:run_safe"],
                "ts_utc": "2026-03-11T12:29:00Z",
                "operator_status": "PENDING",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )
    ledger_path = log_dir / "decision_log.jsonl"
    ledger_path.write_text(
        json.dumps(
            {
                "event": "PROPOSAL_CREATED",
                "decision_id": "decision_safe",
                "trace_id": "trace_safe",
                "ts_utc": "2026-03-11T12:29:00Z",
                "operator_status": "PENDING",
                "proposed_action": "ESCALATE",
                "evidence_refs": ["proof_pack:run_safe"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    latest_before = latest_path.read_text(encoding="utf-8")
    ledger_before = ledger_path.read_text(encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/history?limit=20")

    assert response.status_code == 200
    assert latest_path.read_text(encoding="utf-8") == latest_before
    assert ledger_path.read_text(encoding="utf-8") == ledger_before


def test_execute_endpoint_rejects_when_no_latest_decision_exists(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    (runtime_root / "state").mkdir(parents=True)
    (observability_root / "logs").mkdir(parents=True)

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.post("/api/decisions/latest/execute", json={})

    assert response.status_code == 409
    assert response.json() == {"ok": False, "error": "latest_decision_missing"}


def test_execute_endpoint_rejects_when_latest_decision_is_pending(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    (observability_root / "logs").mkdir(parents=True)
    latest_path = state_dir / "decision_latest.json"
    decision_id = make_decision_id(
        trace_id="trace_pending",
        ts_utc="2026-03-11T13:00:00Z",
        signal_received="MISSING_PROOF",
        proposed_action="REVIEW_PROOF",
    )
    latest_path.write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace_pending",
                "signal_received": "MISSING_PROOF",
                "proposed_action": "REVIEW_PROOF",
                "evidence_refs": ["proof_pack:pending"],
                "ts_utc": "2026-03-11T13:00:00Z",
                "operator_status": "PENDING",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.post("/api/decisions/latest/execute", json={})

    assert response.status_code == 409
    assert response.json() == {"ok": False, "error": "latest_decision_not_approved"}


def test_execute_endpoint_rejects_when_latest_decision_is_rejected(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    (observability_root / "logs").mkdir(parents=True)
    latest_path = state_dir / "decision_latest.json"
    decision_id = make_decision_id(
        trace_id="trace_rejected",
        ts_utc="2026-03-11T13:01:00Z",
        signal_received="UNKNOWN",
        proposed_action="ESCALATE",
    )
    latest_path.write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace_rejected",
                "signal_received": "UNKNOWN",
                "proposed_action": "ESCALATE",
                "evidence_refs": ["proof_pack:rejected"],
                "ts_utc": "2026-03-11T13:01:00Z",
                "operator_status": "REJECTED",
                "operator_note": "no",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.post("/api/decisions/latest/execute", json={})

    assert response.status_code == 409
    assert response.json() == {"ok": False, "error": "latest_decision_not_approved"}


def test_execute_endpoint_rejects_approved_no_action(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    (observability_root / "logs").mkdir(parents=True)
    latest_path = state_dir / "decision_latest.json"
    decision_id = make_decision_id(
        trace_id="trace_no_action",
        ts_utc="2026-03-11T13:02:00Z",
        signal_received="COMPLETE",
        proposed_action="NO_ACTION",
    )
    latest_path.write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace_no_action",
                "signal_received": "COMPLETE",
                "proposed_action": "NO_ACTION",
                "evidence_refs": ["proof_pack:complete"],
                "ts_utc": "2026-03-11T13:02:00Z",
                "operator_status": "APPROVED",
                "operator_note": "noop",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.post("/api/decisions/latest/execute", json={})

    assert response.status_code == 409
    assert response.json() == {"ok": False, "error": "no_action_not_executable"}


def test_execute_endpoint_accepts_approved_executable_action_and_preserves_linkage(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    (observability_root / "logs").mkdir(parents=True)
    latest_path = state_dir / "decision_latest.json"
    decision_id = make_decision_id(
        trace_id="trace_exec",
        ts_utc="2026-03-11T13:03:00Z",
        signal_received="MISSING_PROOF",
        proposed_action="REVIEW_PROOF",
    )
    latest_path.write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace_exec",
                "signal_received": "MISSING_PROOF",
                "proposed_action": "REVIEW_PROOF",
                "evidence_refs": ["proof_pack:run_exec"],
                "ts_utc": "2026-03-11T13:03:00Z",
                "operator_status": "APPROVED",
                "operator_note": "review it",
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_submit_task(task, *, task_id=None):
        captured["task"] = task
        captured["task_id"] = task_id
        return {
            "status": "submitted",
            "task_id": task_id,
            "trace_id": task.get("trace_id"),
            "inbox_path": f"interface/inbox/{task_id}.yaml",
            "ts": "2026-03-11T13:04:00Z",
        }

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(control_plane_execution_bridge, "_submit_task", fake_submit_task)

    response = client.post("/api/decisions/latest/execute", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["bridge_status"] == "HANDOFF_ACCEPTED"
    assert payload["decision_id"] == decision_id
    assert payload["trace_id"] == "trace_exec"
    assert payload["requested_action"] == "REVIEW_PROOF"
    task = captured["task"]
    assert isinstance(task, dict)
    assert task["intent"] == "control.review_proof"
    assert task["trace_id"] == "trace_exec"
    assert task["ops"][0]["type"] == "write_text"
    assert task["ops"][0]["target_path"] == f"runtime/state/execution_requests/{decision_id}.json"
    assert f"\"decision_id\": \"{decision_id}\"" in task["ops"][0]["content"]
    assert "\"trace_id\": \"trace_exec\"" in task["ops"][0]["content"]
    assert "\"requested_action\": \"REVIEW_PROOF\"" in task["ops"][0]["content"]
    rows = [
        json.loads(line)
        for line in (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[-1]["event"] == "EXECUTION_HANDOFF_ACCEPTED"
    assert rows[-1]["decision_id"] == decision_id


def test_execute_endpoint_preserves_append_only_audit_behavior(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    state_dir = runtime_root / "state"
    log_dir = observability_root / "logs"
    state_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    latest_path = state_dir / "decision_latest.json"
    decision_id = make_decision_id(
        trace_id="trace_audit",
        ts_utc="2026-03-11T13:05:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    latest_path.write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace_audit",
                "signal_received": "INCONSISTENT",
                "proposed_action": "QUARANTINE",
                "evidence_refs": ["proof_pack:audit"],
                "ts_utc": "2026-03-11T13:05:00Z",
                "operator_status": "APPROVED",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )
    ledger_path = log_dir / "decision_log.jsonl"
    ledger_path.write_text(
        json.dumps(
            {
                "event": "OPERATOR_APPROVED",
                "decision_id": decision_id,
                "trace_id": "trace_audit",
                "ts_utc": "2026-03-11T13:05:00Z",
                "operator_status": "APPROVED",
                "proposed_action": "QUARANTINE",
                "evidence_refs": ["proof_pack:audit"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda task, *, task_id=None: {
            "status": "submitted",
            "task_id": task_id,
            "trace_id": task.get("trace_id"),
            "inbox_path": f"interface/inbox/{task_id}.yaml",
            "ts": "2026-03-11T13:06:00Z",
        },
    )
    before = ledger_path.read_text(encoding="utf-8")

    response = client.post("/api/decisions/latest/execute", json={})

    assert response.status_code == 200
    after = ledger_path.read_text(encoding="utf-8")
    assert after.startswith(before)
    assert len(after.splitlines()) == len(before.splitlines()) + 1


def test_execute_endpoint_does_not_allow_free_text_execution_or_other_hooks(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    observability_root = tmp_path / "observability"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    (observability_root / "logs").mkdir(parents=True)
    latest_path = state_dir / "decision_latest.json"
    decision_id = make_decision_id(
        trace_id="trace_safe_exec",
        ts_utc="2026-03-11T13:07:00Z",
        signal_received="UNKNOWN",
        proposed_action="ESCALATE",
    )
    latest_path.write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace_safe_exec",
                "signal_received": "UNKNOWN",
                "proposed_action": "ESCALATE",
                "evidence_refs": ["proof_pack:safe_exec"],
                "ts_utc": "2026-03-11T13:07:00Z",
                "operator_status": "APPROVED",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_submit_task(task, *, task_id=None):
        captured["task"] = task
        return {
            "status": "submitted",
            "task_id": task_id,
            "trace_id": task.get("trace_id"),
            "inbox_path": f"interface/inbox/{task_id}.yaml",
            "ts": "2026-03-11T13:08:00Z",
        }

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(control_plane_execution_bridge, "_submit_task", fake_submit_task)
    monkeypatch.setattr(mission_control_server, "enqueue_remediation_queue", lambda **_: (_ for _ in ()).throw(AssertionError("no remediation queue")))
    monkeypatch.setattr(mission_control_server, "apply_approval_action", lambda **_: (_ for _ in ()).throw(AssertionError("no approval flow")))

    response = client.post("/api/decisions/latest/execute", json={})

    assert response.status_code == 200
    task = captured["task"]
    assert isinstance(task, dict)
    assert "command" not in json.dumps(task, sort_keys=True)
    assert task["intent"] == "control.escalate"


def test_latest_decision_has_null_execution_when_no_handoff_exists(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    (runtime_root / "state").mkdir(parents=True)
    observability_root.mkdir(parents=True)
    decision_id = make_decision_id(
        trace_id="trace-no-handoff",
        ts_utc="2026-03-11T14:00:00Z",
        signal_received="UNKNOWN",
        proposed_action="ESCALATE",
    )
    (runtime_root / "state" / "decision_latest.json").write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace-no-handoff",
                "signal_received": "UNKNOWN",
                "proposed_action": "ESCALATE",
                "evidence_refs": ["proof_pack:no_handoff"],
                "ts_utc": "2026-03-11T14:00:00Z",
                "operator_status": "APPROVED",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    assert response.json()["latest"]["execution"] is None


def test_latest_decision_reconciles_handoff_only(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    (runtime_root / "state").mkdir(parents=True)
    (observability_root / "logs").mkdir(parents=True)
    decision_id = make_decision_id(
        trace_id="trace-handoff",
        ts_utc="2026-03-11T14:01:00Z",
        signal_received="MISSING_PROOF",
        proposed_action="REVIEW_PROOF",
    )
    (runtime_root / "state" / "decision_latest.json").write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace-handoff",
                "signal_received": "MISSING_PROOF",
                "proposed_action": "REVIEW_PROOF",
                "evidence_refs": ["proof_pack:handoff"],
                "ts_utc": "2026-03-11T14:01:00Z",
                "operator_status": "APPROVED",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )
    (observability_root / "logs" / "decision_log.jsonl").write_text(
        json.dumps(
            {
                "event": "EXECUTION_HANDOFF_ACCEPTED",
                "decision_id": decision_id,
                "trace_id": "trace-handoff",
                "ts_utc": "2026-03-11T14:01:00Z",
                "operator_status": "APPROVED",
                "proposed_action": "REVIEW_PROOF",
                "evidence_refs": ["proof_pack:handoff"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    execution = response.json()["latest"]["execution"]
    assert execution["bridge_status"] == "HANDOFF_ACCEPTED"
    assert execution["outcome_status"] == "HANDOFF_ONLY"
    assert execution["outcome_ref"] is None


def test_latest_decision_reconciles_trustworthy_success(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    (runtime_root / "state").mkdir(parents=True)
    (observability_root / "logs").mkdir(parents=True)
    outbox_dir.mkdir(parents=True)
    decision_id = make_decision_id(
        trace_id="trace-success",
        ts_utc="2026-03-11T14:02:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    task_id = f"decision_exec_{decision_id}"
    (runtime_root / "state" / "decision_latest.json").write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace-success",
                "signal_received": "INCONSISTENT",
                "proposed_action": "QUARANTINE",
                "evidence_refs": ["proof_pack:success"],
                "ts_utc": "2026-03-11T14:02:00Z",
                "operator_status": "APPROVED",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )
    (observability_root / "logs" / "decision_log.jsonl").write_text(
        json.dumps(
            {
                "event": "EXECUTION_HANDOFF_ACCEPTED",
                "decision_id": decision_id,
                "trace_id": "trace-success",
                "ts_utc": "2026-03-11T14:02:00Z",
                "operator_status": "APPROVED",
                "proposed_action": "QUARANTINE",
                "evidence_refs": ["proof_pack:success"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (outbox_dir / f"{task_id}.result.json").write_text(json.dumps({"status": "committed"}), encoding="utf-8")
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    execution = response.json()["latest"]["execution"]
    assert execution["outcome_status"] == "EXECUTION_SUCCEEDED"
    assert execution["outcome_ref"] == f"interface/outbox/tasks/{task_id}.result.json"


def test_latest_decision_reconciles_trustworthy_failure(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    (runtime_root / "state").mkdir(parents=True)
    (observability_root / "logs").mkdir(parents=True)
    audit_dir.mkdir(parents=True)
    decision_id = make_decision_id(
        trace_id="trace-failed",
        ts_utc="2026-03-11T14:03:00Z",
        signal_received="UNKNOWN",
        proposed_action="ESCALATE",
    )
    task_id = f"decision_exec_{decision_id}"
    (runtime_root / "state" / "decision_latest.json").write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace-failed",
                "signal_received": "UNKNOWN",
                "proposed_action": "ESCALATE",
                "evidence_refs": ["proof_pack:failed"],
                "ts_utc": "2026-03-11T14:03:00Z",
                "operator_status": "APPROVED",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )
    (observability_root / "logs" / "decision_log.jsonl").write_text(
        json.dumps(
            {
                "event": "EXECUTION_HANDOFF_ACCEPTED",
                "decision_id": decision_id,
                "trace_id": "trace-failed",
                "ts_utc": "2026-03-11T14:03:00Z",
                "operator_status": "APPROVED",
                "proposed_action": "ESCALATE",
                "evidence_refs": ["proof_pack:failed"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (audit_dir / f"{task_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    execution = response.json()["latest"]["execution"]
    assert execution["outcome_status"] == "EXECUTION_FAILED"
    assert execution["outcome_ref"] == f"observability/artifacts/router_audit/{task_id}.json"


def test_latest_decision_reconciles_malformed_downstream_result_as_unknown(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    (runtime_root / "state").mkdir(parents=True)
    (observability_root / "logs").mkdir(parents=True)
    outbox_dir.mkdir(parents=True)
    decision_id = make_decision_id(
        trace_id="trace-unknown",
        ts_utc="2026-03-11T14:04:00Z",
        signal_received="MISSING_PROOF",
        proposed_action="REVIEW_PROOF",
    )
    task_id = f"decision_exec_{decision_id}"
    (runtime_root / "state" / "decision_latest.json").write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace-unknown",
                "signal_received": "MISSING_PROOF",
                "proposed_action": "REVIEW_PROOF",
                "evidence_refs": ["proof_pack:unknown"],
                "ts_utc": "2026-03-11T14:04:00Z",
                "operator_status": "APPROVED",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )
    (observability_root / "logs" / "decision_log.jsonl").write_text(
        json.dumps(
            {
                "event": "EXECUTION_HANDOFF_ACCEPTED",
                "decision_id": decision_id,
                "trace_id": "trace-unknown",
                "ts_utc": "2026-03-11T14:04:00Z",
                "operator_status": "APPROVED",
                "proposed_action": "REVIEW_PROOF",
                "evidence_refs": ["proof_pack:unknown"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (outbox_dir / f"{task_id}.result.json").write_text("{bad json", encoding="utf-8")
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(mission_control_server, "enqueue_remediation_queue", lambda **_: (_ for _ in ()).throw(AssertionError("no remediation queue")))
    monkeypatch.setattr(mission_control_server, "apply_approval_action", lambda **_: (_ for _ in ()).throw(AssertionError("no approval flow")))

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    execution = response.json()["latest"]["execution"]
    assert execution["outcome_status"] == "EXECUTION_UNKNOWN"
    assert execution["outcome_ref"] == f"interface/outbox/tasks/{task_id}.result.json"


def _write_latest_decision(
    runtime_root: Path,
    *,
    trace_id: str,
    ts_utc: str,
    signal_received: str,
    proposed_action: str,
    operator_status: str = "APPROVED",
    operator_note: str | None = None,
) -> str:
    decision_id = make_decision_id(
        trace_id=trace_id,
        ts_utc=ts_utc,
        signal_received=signal_received,
        proposed_action=proposed_action,
    )
    (runtime_root / "state").mkdir(parents=True, exist_ok=True)
    (runtime_root / "state" / "decision_latest.json").write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": trace_id,
                "signal_received": signal_received,
                "proposed_action": proposed_action,
                "evidence_refs": [f"proof_pack:{trace_id}"],
                "ts_utc": ts_utc,
                "operator_status": operator_status,
                "operator_note": operator_note,
            }
        ),
        encoding="utf-8",
    )
    return decision_id


def _write_decision_event(
    observability_root: Path,
    *,
    event: str,
    decision_id: str,
    trace_id: str,
    ts_utc: str,
    proposed_action: str,
    operator_status: str = "APPROVED",
    operator_note: str | None = None,
    suggestion: str | None = None,
    confidence_band: str | None = None,
    operator_action: str | None = None,
    alignment: str | None = None,
    policy_verdict: str | None = None,
    policy_reason: str | None = None,
    alignment_count: int | None = None,
) -> None:
    log_path = observability_root / "logs" / "decision_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        payload = {
            "event": event,
            "decision_id": decision_id,
            "trace_id": trace_id,
            "ts_utc": ts_utc,
            "operator_status": operator_status,
            "proposed_action": proposed_action,
            "evidence_refs": [f"proof_pack:{trace_id}"],
            "operator_note": operator_note,
        }
        if suggestion is not None:
            payload["suggestion"] = suggestion
        if confidence_band is not None:
            payload["confidence_band"] = confidence_band
        if operator_action is not None:
            payload["operator_action"] = operator_action
        if alignment is not None:
            payload["alignment"] = alignment
        if policy_verdict is not None:
            payload["policy_verdict"] = policy_verdict
        if policy_reason is not None:
            payload["policy_reason"] = policy_reason
        if alignment_count is not None:
            payload["alignment_count"] = alignment_count
        handle.write(json.dumps(payload) + "\n")


def test_retry_endpoint_accepts_failed_execution_and_increments_retry_count(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-retry",
        ts_utc="2026-03-11T15:00:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-retry",
        ts_utc="2026-03-11T15:00:00Z",
        proposed_action="QUARANTINE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_submit_task(task, *, task_id=None):
        captured["task"] = task
        captured["task_id"] = task_id
        return {"task_id": task_id, "inbox_path": f"interface/inbox/{task_id}.yaml"}

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(control_plane_execution_bridge, "_submit_task", fake_submit_task)

    response = client.post("/api/decisions/latest/retry", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["retry"]["decision_id"] == decision_id
    assert payload["retry"]["retry_count"] == 1
    assert payload["retry"]["requested_action"] == "QUARANTINE"
    assert captured["task_id"] == f"decision_exec_{decision_id}_retry_1"
    ledger_rows = [
        json.loads(line)
        for line in (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    recent_events = [row["event"] for row in ledger_rows[-3:]]
    assert recent_events == [
        "EXECUTION_RETRY_REQUESTED",
        "SUGGESTION_ACCEPTED",
        "POLICY_ALIGNMENT_MATCHED",
    ]

    latest_response = client.get("/api/decisions/latest")
    execution = latest_response.json()["latest"]["execution"]
    assert execution["retry_count"] == 1
    assert execution["outcome_status"] == "HANDOFF_ONLY"


def test_retry_endpoint_accepts_unknown_execution(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-unknown-retry",
        ts_utc="2026-03-11T15:01:00Z",
        signal_received="MISSING_PROOF",
        proposed_action="REVIEW_PROOF",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-unknown-retry",
        ts_utc="2026-03-11T15:01:00Z",
        proposed_action="REVIEW_PROOF",
    )
    (outbox_dir / f"decision_exec_{decision_id}.result.json").write_text("{bad", encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda task, *, task_id=None: {"task_id": task_id, "inbox_path": f"interface/inbox/{task_id}.yaml"},
    )

    response = client.post("/api/decisions/latest/retry", json={})

    assert response.status_code == 200
    assert response.json()["retry"]["requested_action"] == "REVIEW_PROOF"


def test_retry_endpoint_blocks_succeeded_execution(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-success-final",
        ts_utc="2026-03-11T15:02:00Z",
        signal_received="UNKNOWN",
        proposed_action="ESCALATE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-success-final",
        ts_utc="2026-03-11T15:02:00Z",
        proposed_action="ESCALATE",
    )
    (outbox_dir / f"decision_exec_{decision_id}.result.json").write_text(json.dumps({"status": "committed"}), encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no automatic retry")),
    )

    response = client.post("/api/decisions/latest/retry", json={})

    assert response.status_code == 409
    assert response.json() == {"ok": False, "error": "execution_outcome_not_retryable"}


def test_escalate_endpoint_accepts_failed_execution_and_preserves_append_only_history(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-escalate",
        ts_utc="2026-03-11T15:03:00Z",
        signal_received="UNKNOWN",
        proposed_action="ESCALATE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-escalate",
        ts_utc="2026-03-11T15:03:00Z",
        proposed_action="ESCALATE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")
    before_lines = (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8").splitlines()

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda task, *, task_id=None: {"task_id": task_id, "inbox_path": f"interface/inbox/{task_id}.yaml"},
    )

    response = client.post("/api/decisions/latest/escalate", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["escalation"]["decision_id"] == decision_id
    assert payload["escalation"]["requested_action"] == "ESCALATE"
    after_lines = (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert after_lines[: len(before_lines)] == before_lines
    recent_events = [json.loads(row)["event"] for row in after_lines[-3:]]
    assert recent_events == [
        "EXECUTION_ESCALATION_REQUESTED",
        "SUGGESTION_OVERRIDDEN",
        "POLICY_ALIGNMENT_MISMATCHED",
    ]


def test_latest_endpoint_triggers_policy_auto_retry_only_for_narrow_rule(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-passive",
        ts_utc="2026-03-11T15:04:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-passive",
        ts_utc="2026-03-11T15:04:00Z",
        proposed_action="QUARANTINE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-passive",
        ts_utc="2026-03-11T15:04:00Z",
        proposed_action="QUARANTINE",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-passive",
        ts_utc="2026-03-11T15:04:30Z",
        proposed_action="QUARANTINE",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda task, *, task_id=None: captured.update({"task_id": task_id}) or {"task_id": task_id, "inbox_path": f"interface/inbox/{task_id}.yaml"},
    )

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    execution = response.json()["latest"]["execution"]
    assert execution["outcome_status"] == "HANDOFF_ONLY"
    assert execution["policy_execution_status"] == "AUTO RETRY TRIGGERED"
    assert execution["policy_executed"] is True
    assert execution["policy_alignment_count"] == 2
    assert captured["task_id"] == f"decision_exec_{decision_id}_retry_1"
    rows = (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(rows[-2])["event"] == "EXECUTION_RETRY_REQUESTED"
    auto_row = json.loads(rows[-1])
    assert auto_row["event"] == "AUTO_RETRY_TRIGGERED"
    assert auto_row["confidence_band"] == "HIGH"
    assert auto_row["alignment_count"] == 2
    assert auto_row["policy_reason"] == "high_confidence_retry_after_repeated_operator_alignment"

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    rows_after_second_read = (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert rows_after_second_read == rows


def test_latest_endpoint_does_not_auto_retry_when_alignment_count_below_two(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-not-enough-alignment",
        ts_utc="2026-03-11T15:04:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-not-enough-alignment",
        ts_utc="2026-03-11T15:04:00Z",
        proposed_action="QUARANTINE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-not-enough-alignment",
        ts_utc="2026-03-11T15:04:30Z",
        proposed_action="QUARANTINE",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("auto retry must stay blocked")),
    )

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    execution = response.json()["latest"]["execution"]
    assert execution["outcome_status"] == "EXECUTION_FAILED"
    assert execution.get("policy_execution_status") is None


def test_latest_endpoint_does_not_auto_retry_when_policy_confidence_is_not_high(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-medium-confidence",
        ts_utc="2026-03-11T15:05:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-medium-confidence",
        ts_utc="2026-03-11T15:05:00Z",
        proposed_action="QUARANTINE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-medium-confidence",
        ts_utc="2026-03-11T15:05:30Z",
        proposed_action="QUARANTINE",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-medium-confidence",
        ts_utc="2026-03-11T15:05:45Z",
        proposed_action="QUARANTINE",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        mission_control_server,
        "load_decision_policy",
        lambda: {
            "decision_id": decision_id,
            "trace_id": "trace-medium-confidence",
            "suggestion": "RETRY_RECOMMENDED",
            "confidence_band": "MEDIUM",
            "alignment_count": 2,
            "policy_verdict": "HUMAN_APPROVAL_REQUIRED",
            "policy_reason": "retry_recommended_but_not_auto_eligible",
            "policy_safe_lane": "SUPERVISED_RETRY",
        },
    )
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("medium confidence must not auto retry")),
    )

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    assert response.json()["latest"]["execution"]["outcome_status"] == "EXECUTION_FAILED"


def test_latest_endpoint_does_not_auto_retry_when_decision_is_not_approved(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-not-approved",
        ts_utc="2026-03-11T15:06:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
        operator_status="REJECTED",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-not-approved",
        ts_utc="2026-03-11T15:06:00Z",
        proposed_action="QUARANTINE",
        operator_status="REJECTED",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-not-approved",
        ts_utc="2026-03-11T15:06:30Z",
        proposed_action="QUARANTINE",
        operator_status="REJECTED",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-not-approved",
        ts_utc="2026-03-11T15:06:45Z",
        proposed_action="QUARANTINE",
        operator_status="REJECTED",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("non-approved decisions must not auto retry")),
    )

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    assert response.json()["latest"]["operator_status"] == "REJECTED"


def test_latest_endpoint_does_not_auto_retry_when_outcome_is_not_failed(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-succeeded",
        ts_utc="2026-03-11T15:07:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-succeeded",
        ts_utc="2026-03-11T15:07:00Z",
        proposed_action="QUARANTINE",
    )
    (outbox_dir / f"decision_exec_{decision_id}.result.json").write_text(json.dumps({"status": "success"}), encoding="utf-8")
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-succeeded",
        ts_utc="2026-03-11T15:07:30Z",
        proposed_action="QUARANTINE",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-succeeded",
        ts_utc="2026-03-11T15:07:45Z",
        proposed_action="QUARANTINE",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("successful executions must not auto retry")),
    )

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    assert response.json()["latest"]["execution"]["outcome_status"] == "EXECUTION_SUCCEEDED"


def test_latest_endpoint_does_not_auto_trigger_escalation_lane(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-no-auto-escalate",
        ts_utc="2026-03-11T15:08:00Z",
        signal_received="UNKNOWN",
        proposed_action="ESCALATE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-no-auto-escalate",
        ts_utc="2026-03-11T15:08:00Z",
        proposed_action="ESCALATE",
    )
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-no-auto-escalate",
        ts_utc="2026-03-11T15:08:30Z",
        proposed_action="ESCALATE",
        suggestion="ESCALATION_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="ESCALATE_ISSUE",
        alignment="MATCHED_SUGGESTION",
    )
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-no-auto-escalate",
        ts_utc="2026-03-11T15:08:45Z",
        proposed_action="ESCALATE",
        suggestion="ESCALATION_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="ESCALATE_ISSUE",
        alignment="MATCHED_SUGGESTION",
    )

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("escalation must not auto trigger")),
    )

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    latest = response.json()["latest"]
    assert latest["execution"]["outcome_status"] == "HANDOFF_ONLY"
    assert latest["execution"].get("policy_execution_status") is None


def test_frozen_auto_lane_blocks_phase4_1_auto_retry_but_manual_retry_still_works(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-frozen-auto-retry",
        ts_utc="2026-03-11T15:09:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-frozen-auto-retry",
        ts_utc="2026-03-11T15:09:00Z",
        proposed_action="QUARANTINE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-frozen-auto-retry",
        ts_utc="2026-03-11T15:09:30Z",
        proposed_action="QUARANTINE",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-frozen-auto-retry",
        ts_utc="2026-03-11T15:09:45Z",
        proposed_action="QUARANTINE",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_RETRY_REQUESTED",
        decision_id="degraded_seed_2",
        trace_id="trace-seed-2",
        ts_utc="2026-03-11T15:09:50Z",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="AUTO_RETRY_TRIGGERED",
        decision_id="degraded_seed_2",
        trace_id="trace-seed-2",
        ts_utc="2026-03-11T15:09:51Z",
        proposed_action="QUARANTINE",
        confidence_band="HIGH",
        policy_reason="high_confidence_retry_after_repeated_operator_alignment",
        alignment_count=2,
    )
    (audit_dir / "decision_exec_degraded_seed_2_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    captured: list[str] = []
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda task, *, task_id=None: captured.append(task_id) or {"task_id": task_id, "inbox_path": f"interface/inbox/{task_id}.yaml"},
    )

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    latest = response.json()["latest"]
    assert latest["execution"]["outcome_status"] == "EXECUTION_FAILED"
    assert latest["execution"].get("policy_execution_status") is None
    assert captured == []

    retry_response = client.post("/api/decisions/latest/retry", json={})

    assert retry_response.status_code == 200
    assert retry_response.json()["retry"]["requested_action"] == "QUARANTINE"
    assert captured == [f"decision_exec_{decision_id}_retry_1"]


def test_latest_suggestion_returns_retry_for_failed_execution(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-suggest-retry",
        ts_utc="2026-03-11T16:10:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-suggest-retry",
        ts_utc="2026-03-11T16:10:00Z",
        proposed_action="QUARANTINE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/latest/suggestion")

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggestion"] == "RETRY_RECOMMENDED"
    assert payload["confidence_score"] == 0.9
    assert payload["confidence_band"] == "HIGH"
    assert payload["reason"] == "execution_failed_after_approved_decision"
    assert payload["root_cause_hint"] == "deterministic execution failure observed after approved handoff"


def test_latest_suggestion_returns_escalation_for_unknown_execution(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-suggest-escalate",
        ts_utc="2026-03-11T16:11:00Z",
        signal_received="MISSING_PROOF",
        proposed_action="REVIEW_PROOF",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-suggest-escalate",
        ts_utc="2026-03-11T16:11:00Z",
        proposed_action="REVIEW_PROOF",
    )
    (outbox_dir / f"decision_exec_{decision_id}.result.json").write_text("{bad", encoding="utf-8")
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/latest/suggestion")

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggestion"] == "ESCALATION_RECOMMENDED"
    assert payload["confidence_score"] == 0.65
    assert payload["confidence_band"] == "MEDIUM"
    assert payload["reason"] == "execution_outcome_unknown_after_approved_decision"
    assert payload["root_cause_hint"] == "downstream result not safely reconcilable from current execution surfaces"


def test_latest_suggestion_returns_no_action_for_succeeded_execution(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-suggest-success",
        ts_utc="2026-03-11T16:12:00Z",
        signal_received="UNKNOWN",
        proposed_action="ESCALATE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-suggest-success",
        ts_utc="2026-03-11T16:12:00Z",
        proposed_action="ESCALATE",
    )
    (outbox_dir / f"decision_exec_{decision_id}.result.json").write_text(json.dumps({"status": "committed"}), encoding="utf-8")
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/latest/suggestion")

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggestion"] == "NO_ACTION_RECOMMENDED"
    assert payload["confidence_score"] == 0.95
    assert payload["confidence_band"] == "HIGH"
    assert payload["reason"] == "execution_succeeded"
    assert payload["root_cause_hint"] == "execution completed successfully; no further action suggested"


def test_latest_suggestion_returns_no_action_when_decision_missing(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    (runtime_root / "state").mkdir(parents=True, exist_ok=True)
    (observability_root / "logs").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/latest/suggestion")

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggestion"] == "NO_ACTION_RECOMMENDED"
    assert payload["confidence_score"] == 0.2
    assert payload["confidence_band"] == "LOW"
    assert payload["reason"] == "no_latest_decision"
    assert payload["root_cause_hint"] == "no latest decision available for suggestion analysis"


def test_latest_policy_returns_manual_only_for_missing_decision(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    (runtime_root / "state").mkdir(parents=True, exist_ok=True)
    (observability_root / "logs").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/latest/policy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_verdict"] == "MANUAL_ONLY"
    assert payload["policy_safe_lane"] == "NONE"
    assert payload["policy_reason"] == "no_latest_decision"
    assert payload["auto_lane_state"] == "AUTO_LANE_ACTIVE"


def test_latest_policy_returns_auto_allowed_for_high_confidence_retry_with_alignment(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-policy-auto",
        ts_utc="2026-03-11T18:00:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-policy-auto",
        ts_utc="2026-03-11T18:00:00Z",
        proposed_action="QUARANTINE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-policy-auto",
        ts_utc="2026-03-11T18:00:00Z",
        proposed_action="QUARANTINE",
        operator_status="APPROVED",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-policy-auto",
        ts_utc="2026-03-11T18:00:30Z",
        proposed_action="QUARANTINE",
        operator_status="APPROVED",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/latest/policy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_verdict"] == "AUTO_ALLOWED"
    assert payload["policy_safe_lane"] == "SUPERVISED_RETRY"
    assert payload["alignment_count"] == 2
    assert payload["auto_lane_state"] == "AUTO_LANE_ACTIVE"


def test_frozen_auto_lane_downgrades_policy_verdict(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-policy-frozen",
        ts_utc="2026-03-11T18:01:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-policy-frozen",
        ts_utc="2026-03-11T18:01:00Z",
        proposed_action="QUARANTINE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-policy-frozen",
        ts_utc="2026-03-11T18:01:30Z",
        proposed_action="QUARANTINE",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-policy-frozen",
        ts_utc="2026-03-11T18:01:45Z",
        proposed_action="QUARANTINE",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_RETRY_REQUESTED",
        decision_id="degraded_seed",
        trace_id="trace-seed",
        ts_utc="2026-03-11T18:01:50Z",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="AUTO_RETRY_TRIGGERED",
        decision_id="degraded_seed",
        trace_id="trace-seed",
        ts_utc="2026-03-11T18:01:51Z",
        proposed_action="QUARANTINE",
        confidence_band="HIGH",
        policy_reason="high_confidence_retry_after_repeated_operator_alignment",
        alignment_count=2,
    )
    (audit_dir / "decision_exec_degraded_seed_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.get("/api/decisions/latest/policy")

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_verdict"] == "HUMAN_APPROVAL_REQUIRED"
    assert payload["policy_verdict_raw"] == "AUTO_ALLOWED"
    assert payload["auto_lane_state"] == "AUTO_LANE_FROZEN"
    assert payload["auto_lane_reason"] == "policy_degraded"
    assert payload["policy_reason"] == "auto_lane_frozen_due_to_policy_degraded"
    rows = (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert any(json.loads(row)["event"] == "POLICY_AUTO_LANE_FROZEN" for row in rows)


def test_policy_endpoint_is_read_only(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    (runtime_root / "state").mkdir(parents=True, exist_ok=True)
    (observability_root / "logs").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    latest_path = runtime_root / "state" / "decision_latest.json"
    ledger_path = observability_root / "logs" / "decision_log.jsonl"
    latest_before = latest_path.exists()
    ledger_before = ledger_path.exists()

    response = client.get("/api/decisions/latest/policy")

    assert response.status_code == 200
    assert latest_path.exists() is latest_before
    assert ledger_path.exists() is ledger_before


def test_policy_endpoint_records_evaluation_event_once_per_policy_state(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-policy-eval",
        ts_utc="2026-03-11T18:02:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-policy-eval",
        ts_utc="2026-03-11T18:02:00Z",
        proposed_action="QUARANTINE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-policy-eval",
        ts_utc="2026-03-11T18:02:30Z",
        proposed_action="QUARANTINE",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )
    _write_decision_event(
        observability_root,
        event="SUGGESTION_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-policy-eval",
        ts_utc="2026-03-11T18:02:45Z",
        proposed_action="QUARANTINE",
        suggestion="RETRY_RECOMMENDED",
        confidence_band="HIGH",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED_SUGGESTION",
    )
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    first = client.get("/api/decisions/latest/policy")
    second = client.get("/api/decisions/latest/policy")

    assert first.status_code == 200
    assert second.status_code == 200
    rows = (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8").splitlines()
    policy_rows = [json.loads(row) for row in rows if json.loads(row)["event"] == "POLICY_EVALUATED"]
    assert len(policy_rows) == 1
    assert policy_rows[0]["policy_verdict"] == "AUTO_ALLOWED"
    assert policy_rows[0]["confidence_band"] == "HIGH"


def test_retry_records_policy_alignment_match(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-policy-match",
        ts_utc="2026-03-11T18:03:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-policy-match",
        ts_utc="2026-03-11T18:03:00Z",
        proposed_action="QUARANTINE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda task, *, task_id=None: {"task_id": task_id, "inbox_path": f"interface/inbox/{task_id}.yaml"},
    )

    response = client.post("/api/decisions/latest/retry", json={})

    assert response.status_code == 200
    feedback = client.get("/api/decisions/latest/suggestion-feedback").json()
    assert feedback["count"] == 1
    rows = (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8").splitlines()
    policy_rows = [json.loads(row) for row in rows if json.loads(row)["event"] == "POLICY_ALIGNMENT_MATCHED"]
    assert len(policy_rows) == 1
    assert policy_rows[0]["operator_action"] == "RETRY_EXECUTION"
    assert policy_rows[0]["alignment"] == "MATCHED"
    assert policy_rows[0]["policy_verdict"] == "HUMAN_APPROVAL_REQUIRED"


def test_ignore_records_policy_alignment_mismatch(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-policy-mismatch",
        ts_utc="2026-03-11T18:04:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-policy-mismatch",
        ts_utc="2026-03-11T18:04:00Z",
        proposed_action="QUARANTINE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.post("/api/decisions/latest/suggestion-feedback/ignore", json={})

    assert response.status_code == 200
    rows = (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8").splitlines()
    policy_rows = [json.loads(row) for row in rows if json.loads(row)["event"] == "POLICY_ALIGNMENT_MISMATCHED"]
    assert len(policy_rows) == 1
    assert policy_rows[0]["operator_action"] == "IGNORE_SUGGESTION"
    assert policy_rows[0]["alignment"] == "MISMATCHED"


def test_policy_stats_endpoint_returns_aggregates_and_drift_warning(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    audit_dir = repo_root / "observability" / "artifacts" / "router_audit"
    (runtime_root / "state").mkdir(parents=True, exist_ok=True)
    outbox_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    _write_decision_event(
        observability_root,
        event="EXECUTION_RETRY_REQUESTED",
        decision_id="decision_a",
        trace_id="trace-a",
        ts_utc="2026-03-11T18:05:00Z",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="AUTO_RETRY_TRIGGERED",
        decision_id="decision_a",
        trace_id="trace-a",
        ts_utc="2026-03-11T18:05:01Z",
        proposed_action="QUARANTINE",
        confidence_band="HIGH",
        policy_reason="high_confidence_retry_after_repeated_operator_alignment",
        alignment_count=2,
    )
    (outbox_dir / "decision_exec_decision_a_retry_1.result.json").write_text(json.dumps({"status": "success"}), encoding="utf-8")
    _write_decision_event(
        observability_root,
        event="EXECUTION_RETRY_REQUESTED",
        decision_id="decision_b",
        trace_id="trace-b",
        ts_utc="2026-03-11T18:06:00Z",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="AUTO_RETRY_TRIGGERED",
        decision_id="decision_b",
        trace_id="trace-b",
        ts_utc="2026-03-11T18:06:01Z",
        proposed_action="QUARANTINE",
        confidence_band="HIGH",
        policy_reason="high_confidence_retry_after_repeated_operator_alignment",
        alignment_count=2,
    )
    (audit_dir / "decision_exec_decision_b_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")
    _write_decision_event(
        observability_root,
        event="POLICY_ALIGNMENT_MATCHED",
        decision_id="decision_a",
        trace_id="trace-a",
        ts_utc="2026-03-11T18:06:30Z",
        proposed_action="QUARANTINE",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED",
        policy_verdict="AUTO_ALLOWED",
    )
    _write_decision_event(
        observability_root,
        event="POLICY_ALIGNMENT_MISMATCHED",
        decision_id="decision_b",
        trace_id="trace-b",
        ts_utc="2026-03-11T18:06:45Z",
        proposed_action="QUARANTINE",
        operator_action="IGNORE_SUGGESTION",
        alignment="MISMATCHED",
        policy_verdict="AUTO_ALLOWED",
    )
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("policy stats must stay read-only")),
    )

    response = client.get("/api/policy/stats")

    assert response.status_code == 200
    payload = response.json()
    assert payload["auto_retry_triggered"] == 2
    assert payload["auto_retry_success"] == 1
    assert payload["auto_retry_failed"] == 1
    assert payload["alignment_match"] == 1
    assert payload["alignment_mismatch"] == 1
    assert payload["success_rate"] == 0.5
    assert payload["policy_state"] == "POLICY_DEGRADED"
    assert payload["auto_lane_state"] == "AUTO_LANE_FROZEN"
    assert payload["auto_lane_reason"] == "policy_degraded"
    assert payload["warning"] == "Policy reliability degraded. Review recommended."


def test_policy_review_endpoint_returns_safe_sparse_surface(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    (runtime_root / "state").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("policy review must stay read-only")),
    )

    response = client.get("/api/policy/review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["review_flags"] == ["review_insufficient_evidence"]
    assert payload["review_summary"] == "insufficient evidence for strong review conclusions"
    assert payload["reason_breakdown"] == []


def test_policy_review_endpoint_surfaces_flags_and_reason_breakdown(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    audit_dir = repo_root / "observability" / "artifacts" / "router_audit"
    (runtime_root / "state").mkdir(parents=True, exist_ok=True)
    outbox_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    for index in range(1, 5):
        decision_id = f"decision_{index}"
        _write_decision_event(
            observability_root,
            event="POLICY_EVALUATED",
            decision_id=decision_id,
            trace_id=f"trace-{index}",
            ts_utc=f"2026-03-11T20:0{index}:00Z",
            proposed_action="QUARANTINE",
            policy_verdict="AUTO_ALLOWED",
            policy_reason="high_confidence_retry_after_repeated_operator_alignment",
        )
        _write_decision_event(
            observability_root,
            event="EXECUTION_RETRY_REQUESTED",
            decision_id=decision_id,
            trace_id=f"trace-{index}",
            ts_utc=f"2026-03-11T20:0{index}:10Z",
            proposed_action="QUARANTINE",
        )
        _write_decision_event(
            observability_root,
            event="AUTO_RETRY_TRIGGERED",
            decision_id=decision_id,
            trace_id=f"trace-{index}",
            ts_utc=f"2026-03-11T20:0{index}:20Z",
            proposed_action="QUARANTINE",
            confidence_band="HIGH",
            policy_reason="high_confidence_retry_after_repeated_operator_alignment",
            alignment_count=2,
        )
    _write_decision_event(
        observability_root,
        event="POLICY_ALIGNMENT_MATCHED",
        decision_id="decision_1",
        trace_id="trace-1",
        ts_utc="2026-03-11T20:10:00Z",
        proposed_action="QUARANTINE",
        operator_action="RETRY_EXECUTION",
        alignment="MATCHED",
        policy_verdict="AUTO_ALLOWED",
    )
    for index in range(2, 5):
        _write_decision_event(
            observability_root,
            event="POLICY_ALIGNMENT_MISMATCHED",
            decision_id=f"decision_{index}",
            trace_id=f"trace-{index}",
            ts_utc=f"2026-03-11T20:1{index}:00Z",
            proposed_action="QUARANTINE",
            operator_action="IGNORE_SUGGESTION",
            alignment="MISMATCHED",
            policy_verdict="AUTO_ALLOWED",
        )

    (audit_dir / "decision_exec_decision_1_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")
    (audit_dir / "decision_exec_decision_2_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")
    (audit_dir / "decision_exec_decision_3_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")
    (outbox_dir / "decision_exec_decision_4_retry_1.result.json").write_text(json.dumps({"status": "success"}), encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("policy review must stay read-only")),
    )

    response = client.get("/api/policy/review")

    assert response.status_code == 200
    payload = response.json()
    assert payload["policy_state"] == "POLICY_DEGRADED"
    assert payload["auto_lane_state"] == "AUTO_LANE_FROZEN"
    assert payload["totals"]["policy_evaluations"] == 4
    assert payload["rates"]["auto_retry_success_rate"] == 0.25
    assert payload["rates"]["operator_alignment_rate"] == 0.25
    assert "review_auto_retry_threshold" in payload["review_flags"]
    assert "review_alignment_drift" in payload["review_flags"]
    assert "review_frozen_lane" in payload["review_flags"]
    assert "review_reason_failure_cluster" in payload["review_flags"]
    assert payload["reason_breakdown"][0]["policy_reason"] == "high_confidence_retry_after_repeated_operator_alignment"
    assert payload["reason_breakdown"][0]["failure_count"] == 3


def test_policy_auto_lane_unfreeze_requires_frozen_state_and_appends_audit(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    outbox_dir = repo_root / "interface" / "outbox" / "tasks"
    audit_dir = repo_root / "observability" / "artifacts" / "router_audit"
    (runtime_root / "state").mkdir(parents=True, exist_ok=True)
    outbox_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)

    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-unfreeze",
        ts_utc="2026-03-11T19:00:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
        operator_status="APPROVED",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_RETRY_REQUESTED",
        decision_id="decision_a",
        trace_id="trace-a",
        ts_utc="2026-03-11T18:05:00Z",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="AUTO_RETRY_TRIGGERED",
        decision_id="decision_a",
        trace_id="trace-a",
        ts_utc="2026-03-11T18:05:01Z",
        proposed_action="QUARANTINE",
        confidence_band="HIGH",
        policy_reason="high_confidence_retry_after_repeated_operator_alignment",
        alignment_count=2,
    )
    (audit_dir / "decision_exec_decision_a_retry_1.json").write_text(json.dumps({"decision": "error"}), encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unfreeze must not trigger execution")),
    )

    response = client.post(
        "/api/policy/auto-lane/unfreeze",
        json={"operator_note": "manual review completed; re-enable narrow retry lane"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["auto_lane_state"] == "AUTO_LANE_ACTIVE"
    assert payload["reason"] == "manual_policy_review_completed"

    stats = client.get("/api/policy/stats").json()
    assert stats["auto_lane_state"] == "AUTO_LANE_ACTIVE"
    assert stats["auto_lane_reason"] == "manual_policy_review_completed"
    assert stats["auto_lane_lifecycle_event"] == "POLICY_AUTO_LANE_UNFROZEN"
    assert stats["auto_lane_operator_note"] == "manual review completed; re-enable narrow retry lane"

    rows = [
        json.loads(line)
        for line in (observability_root / "logs" / "decision_log.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(row["event"] == "POLICY_AUTO_LANE_UNFREEZE_REQUESTED" for row in rows)
    assert any(row["event"] == "POLICY_AUTO_LANE_UNFROZEN" for row in rows)
    assert rows[-1]["decision_id"] == decision_id


def test_policy_auto_lane_unfreeze_fails_closed_when_not_frozen(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    (runtime_root / "state").mkdir(parents=True, exist_ok=True)

    _write_latest_decision(
        runtime_root,
        trace_id="trace-not-frozen",
        ts_utc="2026-03-11T19:10:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
        operator_status="APPROVED",
    )

    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.post("/api/policy/auto-lane/unfreeze", json={})

    assert response.status_code == 409
    assert response.json()["error"] == "auto_lane_not_frozen"


def test_retry_records_suggestion_accepted_feedback(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-feedback-retry",
        ts_utc="2026-03-11T17:00:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-feedback-retry",
        ts_utc="2026-03-11T17:00:00Z",
        proposed_action="QUARANTINE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda task, *, task_id=None: {"task_id": task_id, "inbox_path": f"interface/inbox/{task_id}.yaml"},
    )

    response = client.post("/api/decisions/latest/retry", json={})

    assert response.status_code == 200
    feedback = client.get("/api/decisions/latest/suggestion-feedback").json()
    assert feedback["count"] == 1
    item = feedback["items"][0]
    assert item["event"] == "SUGGESTION_ACCEPTED"
    assert item["operator_action"] == "RETRY_EXECUTION"
    assert item["alignment"] == "MATCHED_SUGGESTION"
    assert item["suggestion"] == "RETRY_RECOMMENDED"
    assert item["confidence_band"] == "HIGH"


def test_ignore_suggestion_records_ignored_feedback(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-feedback-ignore",
        ts_utc="2026-03-11T17:01:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-feedback-ignore",
        ts_utc="2026-03-11T17:01:00Z",
        proposed_action="QUARANTINE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)

    response = client.post("/api/decisions/latest/suggestion-feedback/ignore", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["feedback"]["alignment"] == "IGNORED_SUGGESTION"
    feedback = client.get("/api/decisions/latest/suggestion-feedback").json()
    assert feedback["items"][0]["event"] == "SUGGESTION_IGNORED"
    assert feedback["items"][0]["operator_action"] == "IGNORE_SUGGESTION"


def test_escalation_records_overridden_feedback_when_retry_was_suggested(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    repo_root = tmp_path / "repo"
    runtime_root = tmp_path / "runtime"
    observability_root = repo_root / "observability"
    audit_dir = observability_root / "artifacts" / "router_audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    decision_id = _write_latest_decision(
        runtime_root,
        trace_id="trace-feedback-override",
        ts_utc="2026-03-11T17:02:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    _write_decision_event(
        observability_root,
        event="EXECUTION_HANDOFF_ACCEPTED",
        decision_id=decision_id,
        trace_id="trace-feedback-override",
        ts_utc="2026-03-11T17:02:00Z",
        proposed_action="QUARANTINE",
    )
    (audit_dir / f"decision_exec_{decision_id}.json").write_text(json.dumps({"decision": "rejected"}), encoding="utf-8")
    monkeypatch.setattr(mission_control_server, "ROOT", repo_root)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)
    monkeypatch.setattr(mission_control_server, "_observability_root", lambda: observability_root)
    monkeypatch.setattr(
        control_plane_execution_bridge,
        "_submit_task",
        lambda task, *, task_id=None: {"task_id": task_id, "inbox_path": f"interface/inbox/{task_id}.yaml"},
    )

    response = client.post("/api/decisions/latest/escalate", json={})

    assert response.status_code == 200
    feedback = client.get("/api/decisions/latest/suggestion-feedback").json()
    item = feedback["items"][0]
    assert item["event"] == "SUGGESTION_OVERRIDDEN"
    assert item["operator_action"] == "ESCALATE_ISSUE"
    assert item["alignment"] == "OVERRIDDEN"
    assert item["suggestion"] == "RETRY_RECOMMENDED"
