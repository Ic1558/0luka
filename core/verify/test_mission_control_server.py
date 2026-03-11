from __future__ import annotations

import json
import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server
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
        }
    }


def test_decisions_latest_returns_null_when_missing(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    (runtime_root / "state").mkdir(parents=True)
    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    assert response.json() == {"pending": None}


def test_decisions_latest_handles_malformed_latest_gracefully(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    latest_path = state_dir / "decision_latest.json"
    latest_path.write_text("{bad-json", encoding="utf-8")
    before = latest_path.read_text(encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    assert response.json() == {"pending": None}
    assert latest_path.read_text(encoding="utf-8") == before


def test_decisions_latest_returns_null_for_non_pending_latest(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    decision_id = make_decision_id(
        trace_id="trace-124",
        ts_utc="2026-03-11T12:01:00Z",
        signal_received="INCONSISTENT",
        proposed_action="QUARANTINE",
    )
    (state_dir / "decision_latest.json").write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace-124",
                "signal_received": "INCONSISTENT",
                "proposed_action": "QUARANTINE",
                "evidence_refs": ["proof_pack:run_124"],
                "ts_utc": "2026-03-11T12:01:00Z",
                "operator_status": "APPROVED",
                "operator_note": "done",
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)

    response = client.get("/api/decisions/latest")

    assert response.status_code == 200
    assert response.json() == {"pending": None}


def test_decisions_latest_performs_no_file_writes_and_no_mutation_routes_exist(tmp_path, monkeypatch) -> None:
    client = TestClient(mission_control_server.app)
    runtime_root = tmp_path / "runtime"
    state_dir = runtime_root / "state"
    state_dir.mkdir(parents=True)
    latest_path = state_dir / "decision_latest.json"
    decision_id = make_decision_id(
        trace_id="trace-125",
        ts_utc="2026-03-11T12:02:00Z",
        signal_received="UNKNOWN",
        proposed_action="ESCALATE",
    )
    latest_path.write_text(
        json.dumps(
            {
                "decision_id": decision_id,
                "trace_id": "trace-125",
                "signal_received": "UNKNOWN",
                "proposed_action": "ESCALATE",
                "evidence_refs": ["proof_pack:run_125"],
                "ts_utc": "2026-03-11T12:02:00Z",
                "operator_status": "PENDING",
                "operator_note": None,
            }
        ),
        encoding="utf-8",
    )
    before = latest_path.read_text(encoding="utf-8")

    monkeypatch.setattr(mission_control_server, "_runtime_root", lambda: runtime_root)

    get_response = client.get("/api/decisions/latest")
    post_response = client.post("/api/decisions/latest", json={})

    assert get_response.status_code == 200
    assert latest_path.read_text(encoding="utf-8") == before
    assert not (state_dir / "decision_latest.json.tmp").exists()
    assert post_response.status_code == 405
