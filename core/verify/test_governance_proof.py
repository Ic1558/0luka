import json
import pytest
import os
from pathlib import Path
from tools.ops.dod_checker import (
    Paths,
    check_activity_events,
    PROOF_MODE_SYNTHETIC,
    PROOF_MODE_OPERATIONAL,
    EMIT_MODE_MANUAL,
    EMIT_MODE_AUTO,
)

@pytest.fixture
def mock_paths(tmp_path):
    root = tmp_path
    feed = root / "activity_feed.jsonl"
    feed.write_text("")
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
        {"phase": "P1", "action": "started", "ts_utc": "2026-01-01T00:00:00Z", "emit_mode": EMIT_MODE_AUTO},
        {"phase": "P1", "action": "completed", "ts_utc": "2026-01-01T00:00:10Z", "emit_mode": EMIT_MODE_MANUAL},
        {"phase": "P1", "action": "verified", "ts_utc": "2026-01-01T00:00:20Z", "emit_mode": EMIT_MODE_AUTO},
    ]
    with mock_paths.activity_feed.open("w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    
    res = check_activity_events("P1", mock_paths)
    assert res["proof_mode"] == PROOF_MODE_SYNTHETIC

def test_proof_mode_operational(mock_paths):
    # Setup: 3 events, all auto
    events = [
        {"phase": "P1", "action": "started", "ts_utc": "2026-01-01T00:00:00Z", "emit_mode": EMIT_MODE_AUTO},
        {"phase": "P1", "action": "completed", "ts_utc": "2026-01-01T00:00:10Z", "emit_mode": EMIT_MODE_AUTO},
        {"phase": "P1", "action": "verified", "ts_utc": "2026-01-01T00:00:20Z", "emit_mode": EMIT_MODE_AUTO},
    ]
    with mock_paths.activity_feed.open("w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    
    res = check_activity_events("P1", mock_paths)
    assert res["proof_mode"] == PROOF_MODE_OPERATIONAL

def test_proof_mode_missing_fields_defaults_to_synthetic(mock_paths):
    # Setup: legacy events without emit_mode
    events = [
        {"phase": "P1", "action": "started", "ts_utc": "2026-01-01T00:00:00Z"},
        {"phase": "P1", "action": "completed", "ts_utc": "2026-01-01T00:00:10Z"},
        {"phase": "P1", "action": "verified", "ts_utc": "2026-01-01T00:00:20Z"},
    ]
    with mock_paths.activity_feed.open("w") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    
    res = check_activity_events("P1", mock_paths)
    assert res["proof_mode"] == PROOF_MODE_SYNTHETIC
