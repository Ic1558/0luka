from __future__ import annotations

import sys
from pathlib import Path

from starlette.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from interface.operator import mission_control_server


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
