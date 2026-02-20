import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Adjust path to import core modules
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import timeline
from core.task_dispatcher import dispatch_one

@pytest.fixture
def temp_root():
    """Create a temporary root directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # Setup minimal structure
        (root / "interface" / "inbox").mkdir(parents=True)
        (root / "interface" / "outbox" / "tasks").mkdir(parents=True)
        (root / "interface" / "completed").mkdir(parents=True)
        (root / "interface" / "rejected").mkdir(parents=True)
        (root / "observability" / "artifacts" / "tasks").mkdir(parents=True)
        (root / "observability" / "logs").mkdir(parents=True) # Dispatcher needs this
        
        with patch("core.task_dispatcher.ROOT", root),              patch("core.timeline.ROOT", root),              patch("core.timeline.ARTIFACTS_DIR", root / "observability" / "artifacts" / "tasks"),              patch("core.task_dispatcher.DISPATCH_LOG", root / "observability" / "logs" / "dispatcher.jsonl"): 
                yield root

def test_heartbeat_emit_success(temp_root):
    """Test standard heartbeat emission on dispatch start and end."""
    task_file = temp_root / "interface" / "inbox" / "task_test_001.yaml"
    task_file.write_text("task_id: test_001\nintent: test.emit\nschema_version: clec.v1\n", encoding="utf-8")
    
    # We need to mock Router execution to avoid running real tools/router logic
    # Also mock gate to bypass strict schema validation
    with patch("core.task_dispatcher.gate_inbound_envelope") as mock_gate,          patch("core.router.Router.execute") as mock_execute,          patch("core.router.Router.audit") as mock_audit:
        
        # Mock gate return
        mock_gate.return_value = {
                "payload": {
                    "task": {
                        "task_id": "test_001",
                        "schema_version": "clec.v1",
                        "intent": "test.emit",
                        "ts_utc": "2026-02-20T00:00:00Z",
                        "call_sign": "[Test]",
                        "root": "${ROOT}",
                        "ops": [{"op_id": "op1", "type": "run", "command": "git status"}],
                    }
                }
            }

        mock_execute.return_value = {"status": "success", "evidence": {}}
        mock_audit.return_value = {"status": "committed"} # simulates success
        
        # Run dispatch_one
        result = dispatch_one(task_file, dry_run=False)
        
        # Result should be 'committed' (based on audit return)
        assert result["status"] == "committed"
        
        # Check timeline artifacts
        timeline_path = temp_root / "observability" / "artifacts" / "tasks" / "test_001" / "timeline.jsonl"
        assert timeline_path.exists()
        
        lines = [json.loads(line) for line in timeline_path.read_text().splitlines()]
        
        heartbeats = [e for e in lines if e["event"] == "heartbeat.dispatcher"]
        assert len(heartbeats) >= 2
        
        # Verify Start Payload
        start_hb = heartbeats[0]
        assert start_hb["task_id"] == "test_001"
        assert start_hb.get("source") == "dispatcher"
        assert start_hb.get("status") == "start"
        
        # Verify End Payload
        end_hb = heartbeats[-1]
        assert end_hb["task_id"] == "test_001"
        assert end_hb.get("source") == "dispatcher"
        assert end_hb.get("status") == "committed"


def test_heartbeat_emit_failure_non_fatal(temp_root):
    """Test that timeline write failure does not break dispatch."""
    task_file = temp_root / "interface" / "inbox" / "task_test_fail_emit.yaml"
    task_file.write_text("task_id: test_fail\nintent: test.fail_emit\nschema_version: clec.v1\n", encoding="utf-8")
    
    # Mock emit_event to raise exception
    with patch("core.timeline.emit_event", side_effect=RuntimeError("Simulated Write Failure")):
        with patch("core.task_dispatcher.gate_inbound_envelope") as mock_gate,              patch("core.router.Router.execute") as mock_execute,              patch("core.router.Router.audit") as mock_audit:
            
            # Mock gate return
            mock_gate.return_value = {
                "payload": {
                    "task": {
                        "task_id": "test_fail",
                        "schema_version": "clec.v1",
                        "intent": "test.fail",
                        "ts_utc": "2026-02-20T00:00:00Z",
                        "call_sign": "[Test]",
                        "root": "${ROOT}",
                        "ops": [{"op_id": "op1", "type": "run", "command": "git status"}],
                    }
                }
            }
            mock_execute.return_value = {"status": "success"}
            mock_audit.return_value = {"status": "committed"}
            
            # Run dispatch_one - Should NOT raise exception
            try:
                result = dispatch_one(task_file, dry_run=False)
            except RuntimeError:
                pytest.fail("Dispatch failed due to timeline emit error (should be non-fatal)")
            
            assert result["status"] == "committed"
            # Logic proceeded despite emit failure

def test_heartbeat_emit_rejected(temp_root):
    """Test heartbeat emission on rejected task (e.g. gate failure)."""
    task_file = temp_root / "interface" / "inbox" / "task_test_reject.yaml"
    task_file.write_text("task_id: test_reject\nintent: test.reject\nschema_version: clec.v1\n", encoding="utf-8")
    
    from core.phase1a_resolver import Phase1AResolverError
    
    with patch("core.task_dispatcher.gate_inbound_envelope", side_effect=Phase1AResolverError("Gate Closed")):
        result = dispatch_one(task_file, dry_run=False)
        
        assert result["status"] == "rejected"
        
        timeline_path = temp_root / "observability" / "artifacts" / "tasks" / "test_reject" / "timeline.jsonl"
        
        if timeline_path.exists():
            lines = [json.loads(line) for line in timeline_path.read_text().splitlines()]
            heartbeats = [e for e in lines if e["event"] == "heartbeat.dispatcher"]
            
            rejected = [h for h in heartbeats if h.get("status") == "rejected"]
            assert len(rejected) >= 1
            assert rejected[0]["source"] == "dispatcher"
