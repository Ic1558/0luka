#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ops.epoch_emitter import main as emitter_main


@pytest.fixture
def runtime_root():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "logs").mkdir()
        yield root


def _write_log(path: Path, lines: list[str]):
    with path.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")


def test_genesis(runtime_root: Path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(runtime_root)
    # Run twice for genesis
    sys_argv = ["epoch_emitter.py", "--json"]
    import sys
    orig_argv = sys.argv
    sys.argv = sys_argv
    
    # We use emitter_main directly, but we need to capture output.
    # To keep it simple, we can call it in a subprocess or use a mock for sys.stdout.
    from io import StringIO
    from unittest.mock import patch
    
    with patch("sys.stdout", new=StringIO()) as fake_out:
        rc = emitter_main()
        assert rc == 0
        output = json.loads(fake_out.getvalue())
        assert output["ok"] is True
        assert output["epoch_id"] == 1
        assert output["record"]["prev_epoch_hash"] == "0" * 64
        
    sys.argv = orig_argv


def test_chain_continuity(runtime_root: Path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(runtime_root)
    sys_argv = ["epoch_emitter.py", "--json"]
    import sys
    orig_argv = sys.argv
    
    from io import StringIO
    from unittest.mock import patch
    
    # Run 1
    with patch("sys.stdout", new=StringIO()) as fake_out:
        sys.argv = sys_argv
        emitter_main()
        output1 = json.loads(fake_out.getvalue())
        hash1 = output1["epoch_hash"]
        
    # Run 2
    with patch("sys.stdout", new=StringIO()) as fake_out:
        sys.argv = sys_argv
        emitter_main()
        output2 = json.loads(fake_out.getvalue())
        assert output2["epoch_id"] == 2
        assert output2["record"]["prev_epoch_hash"] == hash1
        
    sys.argv = orig_argv


def test_epoch_hash_verification(runtime_root: Path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(runtime_root)
    
    # Create some logs
    _write_log(runtime_root / "logs" / "dispatcher.jsonl", ["{\"event\":\"test\"}"])
    
    sys_argv = ["epoch_emitter.py", "--json"]
    import sys
    orig_argv = sys.argv
    
    from io import StringIO
    from unittest.mock import patch
    
    with patch("sys.stdout", new=StringIO()) as fake_out:
        sys.argv = sys_argv
        emitter_main()
        output = json.loads(fake_out.getvalue())
        
        record = output["record"]
        epoch_id = record["epoch_id"]
        prev_hash = record["prev_epoch_hash"]
        log_heads = record["log_heads"]
        
        # Recompute
        material = str(epoch_id) + prev_hash + json.dumps(log_heads, sort_keys=True, separators=(",", ":"))
        expected_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
        
        assert record["epoch_hash"] == expected_hash
        
    sys.argv = orig_argv


def test_dry_run(runtime_root: Path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(runtime_root)
    sys_argv = ["epoch_emitter.py", "--json", "--dry-run"]
    import sys
    orig_argv = sys.argv
    
    from io import StringIO
    from unittest.mock import patch
    
    manifest_path = runtime_root / "logs" / "epoch_manifest.jsonl"
    
    with patch("sys.stdout", new=StringIO()) as fake_out:
        sys.argv = sys_argv
        emitter_main()
        output = json.loads(fake_out.getvalue())
        assert output["ok"] is True
        assert not manifest_path.exists()
        
    sys.argv = orig_argv


def test_missing_log(runtime_root: Path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(runtime_root)
    # Only activity_feed exists
    _write_log(runtime_root / "logs" / "activity_feed.jsonl", ["{\"action\":\"test\"}"])
    
    sys_argv = ["epoch_emitter.py", "--json"]
    import sys
    orig_argv = sys.argv
    
    from io import StringIO
    from unittest.mock import patch
    
    with patch("sys.stdout", new=StringIO()) as fake_out:
        sys.argv = sys_argv
        emitter_main()
        output = json.loads(fake_out.getvalue())
        assert output["ok"] is True
        log_heads = output["record"]["log_heads"]
        assert "activity_feed" in log_heads
        assert "dispatcher" not in log_heads
        assert "rotation_seals" not in log_heads
        
    sys.argv = orig_argv
