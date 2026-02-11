import json
import pytest
import os
from pathlib import Path
from tools.ops.dod_checker import (
    Paths,
    check_activity_events,
    run_check,
    PROOF_MODE_SYNTHETIC,
    PROOF_MODE_OPERATIONAL,
    EMIT_MODE_MANUAL,
    EMIT_MODE_TOOL,
    EMIT_MODE_AUTO,
    VERDICT_PROVEN,
    VERDICT_PARTIAL,
)

@pytest.fixture
def mock_paths(tmp_path):
    root = tmp_path
    feed = root / "activity_feed.jsonl"
    feed.write_text("")
    (root / "docs/dod").mkdir(parents=True)
    (root / "reports").mkdir(parents=True)
    return Paths(
        root=root,
        docs_dod=root / "docs/dod",
        reports_dir=root / "reports",
        activity_feed=feed,
        phase_status=root / "phase_status.yaml"
    )

def test_proof_mode_synthetic(mock_paths):
    # Setup: 3 events, one is manual
    events = [
        {"phase": "P1", "action": "started", "ts_utc": "2026-01-01T00:00:00Z", "emit_mode": EMIT_MODE_AUTO, "verifier_mode": "operational_proof", "ts_epoch_ms": 1, "tool": "test", "run_id": "r1"},
        {"phase": "P1", "action": "completed", "ts_utc": "2026-01-01T00:00:10Z", "emit_mode": EMIT_MODE_MANUAL, "verifier_mode": "synthetic_proof", "ts_epoch_ms": 2, "tool": "test", "run_id": "r1"},
        {"phase": "P1", "action": "verified", "ts_utc": "2026-01-01T00:00:20Z", "emit_mode": EMIT_MODE_AUTO, "verifier_mode": "operational_proof", "ts_epoch_ms": 3, "tool": "test", "run_id": "r1"},
    ]
    with mock_paths.activity_feed.open("w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    
    res = check_activity_events("P1", mock_paths)
    assert res["proof_mode"] == PROOF_MODE_SYNTHETIC
    assert res["taxonomy_ok"] is True

def test_proof_mode_operational(mock_paths):
    # Setup: 3 events, all auto
    events = [
        {"phase": "P1", "action": "started", "ts_utc": "2026-01-01T00:00:00Z", "emit_mode": EMIT_MODE_AUTO, "verifier_mode": "operational_proof", "ts_epoch_ms": 1, "tool": "test", "run_id": "r1"},
        {"phase": "P1", "action": "completed", "ts_utc": "2026-01-01T00:00:10Z", "emit_mode": EMIT_MODE_AUTO, "verifier_mode": "operational_proof", "ts_epoch_ms": 2, "tool": "test", "run_id": "r1"},
        {"phase": "P1", "action": "verified", "ts_utc": "2026-01-01T00:00:20Z", "emit_mode": EMIT_MODE_AUTO, "verifier_mode": "operational_proof", "ts_epoch_ms": 3, "tool": "test", "run_id": "r1"},
    ]
    with mock_paths.activity_feed.open("w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    
    res = check_activity_events("P1", mock_paths)
    assert res["proof_mode"] == PROOF_MODE_OPERATIONAL
    assert res["taxonomy_ok"] is True

def test_taxonomy_incomplete(mock_paths):
    events = [
        {"phase": "P1", "action": "started", "ts_utc": "2026-01-01T00:00:00Z"},
    ]
    with mock_paths.activity_feed.open("w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    
    res = check_activity_events("P1", mock_paths)
    assert "taxonomy.incomplete_event" in res["missing"]
    assert res["taxonomy_ok"] is False

def test_registry_integrity_check(mock_paths):
    # Create DoD file
    dod = mock_paths.docs_dod / "DOD__P1.md"
    dod.write_text("- **Phase / Task ID**: P1\n- **Commit SHA**: hash\n- **Gate**: G1\n- **Related SOT Section**: S1")
    
    # Set registry to PROVEN but NO artifact
    registry = mock_paths.phase_status
    registry.write_text("phases:\n  P1:\n    verdict: PROVEN\n    evidence_path: reports/missing.json")
    
    # Run check
    # We need to mock _git_commit_exists to return True
    import unittest.mock
    with unittest.mock.patch("tools.ops.dod_checker._git_commit_exists", return_value=True):
        res = run_check("P1", mock_paths)
        assert res["verdict"] == VERDICT_PARTIAL
        assert "registry.verdict_without_artifact" in res["missing"]
        assert res["checks"]["registry_integrity_ok"] is False

def test_synthetic_detected_phase_15_5_3(mock_paths):
    # Create DoD file
    phase_id = "PHASE_15_5_3"
    dod = mock_paths.docs_dod / f"DOD__{phase_id}.md"
    dod.write_text(f"- **Phase / Task ID**: {phase_id}\n- **Commit SHA**: hash\n- **Gate**: G1\n- **Related SOT Section**: S1")

    # Setup synthetic chain
    events = [
        {"phase": phase_id, "action": "started", "ts_utc": "2026-01-01T00:00:00Z", "emit_mode": EMIT_MODE_TOOL, "verifier_mode": "synthetic_proof", "ts_epoch_ms": 1},
        {"phase": phase_id, "action": "completed", "ts_utc": "2026-01-01T00:00:10Z", "emit_mode": EMIT_MODE_TOOL, "verifier_mode": "synthetic_proof", "ts_epoch_ms": 2},
        {"phase": phase_id, "action": "verified", "ts_utc": "2026-01-01T00:00:20Z", "emit_mode": EMIT_MODE_TOOL, "verifier_mode": "synthetic_proof", "ts_epoch_ms": 3},
    ]
    with mock_paths.activity_feed.open("w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    import unittest.mock
    with unittest.mock.patch("tools.ops.dod_checker._git_commit_exists", return_value=True):
        res = run_check(phase_id, mock_paths)
        assert res["checks"]["activity_chain"]["proof_mode"] == PROOF_MODE_SYNTHETIC
        assert res["checks"]["synthetic_detected"] is True
