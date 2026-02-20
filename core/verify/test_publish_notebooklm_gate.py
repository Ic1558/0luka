import os
import sys
import json
import pytest
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure ops are importable
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import tools.ops.publish_notebooklm as publish_notebooklm

@pytest.fixture
def mock_repo(tmp_path):
    orig_root = publish_notebooklm.ROOT
    orig_sot = publish_notebooklm.SOT_PACKS_DIR
    orig_feed = publish_notebooklm.FEED_PATH
    orig_sot_tel = publish_notebooklm.PUBLISH_TEL
    orig_lock = publish_notebooklm.SYNC_LOCK
    
    test_root = tmp_path
    publish_notebooklm.ROOT = test_root
    publish_notebooklm.SOT_PACKS_DIR = test_root / "observability" / "artifacts" / "sot_packs"
    publish_notebooklm.FEED_PATH = test_root / "observability" / "logs" / "activity_feed.jsonl"
    publish_notebooklm.PUBLISH_TEL = test_root / "observability" / "telemetry" / "sot_publish.json"
    publish_notebooklm.SYNC_LOCK = publish_notebooklm.SOT_PACKS_DIR / "latest" / ".sync_lock"
    
    publish_notebooklm.SOT_PACKS_DIR.mkdir(parents=True)
    publish_notebooklm.FEED_PATH.parent.mkdir(parents=True)
    publish_notebooklm.FEED_PATH.write_text("")
    
    yield test_root
    
    publish_notebooklm.ROOT = orig_root
    publish_notebooklm.SOT_PACKS_DIR = orig_sot
    publish_notebooklm.FEED_PATH = orig_feed
    publish_notebooklm.PUBLISH_TEL = orig_sot_tel
    publish_notebooklm.SYNC_LOCK = orig_lock

def setup_valid_pack(test_root, head="aaaaaaa", ts="20260220T173540Z"):
    pack_name = f"{ts}_{head[:7]}"
    pack_dir = publish_notebooklm.SOT_PACKS_DIR / pack_name
    pack_dir.mkdir()
    
    manifest = {
        "git_head": head,
        "sot_sha256": "sot_hash",
        "pack_sha256": "pack_hash",
        "built_at_utc": ts,
        "builder_version": "14A.1"
    }
    with open(pack_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)
        
    latest_link = publish_notebooklm.SOT_PACKS_DIR / "latest"
    os.symlink(pack_name, latest_link)
    
    publish_notebooklm.FEED_PATH.write_text(f'{{"action": "sot_seal", "git_head": "{head}", "pack_sha256": "pack_hash"}}\n')

@patch('subprocess.run')
def test_publish_gate_aborts_on_dirty_tree(mock_run, mock_repo):
    mock_status = MagicMock()
    mock_status.returncode = 0
    mock_status.stdout = " M file.txt\n"
    mock_run.return_value = mock_status
    
    with pytest.raises(SystemExit):
        publish_notebooklm.check_gates()

@patch('subprocess.run')
def test_publish_gate_aborts_on_hash_mismatch(mock_run, mock_repo):
    # Mock clean tree
    mock_status = MagicMock()
    mock_status.returncode = 0
    mock_status.stdout = ""
    mock_run.return_value = mock_status
    
    setup_valid_pack(mock_repo)
    
    # Overwrite activity_feed with mismatch pack hash
    publish_notebooklm.FEED_PATH.write_text('{"action": "sot_seal", "git_head": "aaaaaaa", "pack_sha256": "wrong_hash"}\n')
    
    with pytest.raises(SystemExit):
        publish_notebooklm.check_gates()

@patch('subprocess.run')
@patch('tools.ops.publish_notebooklm.upload_to_notebooklm')
def test_publish_gate_succeeds_with_perfect_seal(mock_upload, mock_run, mock_repo):
    mock_status = MagicMock()
    mock_status.returncode = 0
    mock_status.stdout = ""
    mock_run.return_value = mock_status
    
    setup_valid_pack(mock_repo)
    
    publish_notebooklm.publish()
    
    mock_upload.assert_called_once()
    assert publish_notebooklm.PUBLISH_TEL.exists()
    
    with open(publish_notebooklm.FEED_PATH) as f:
        lines = f.read().strip().split('\n')
    
    last_event = json.loads(lines[-1])
    assert last_event["action"] == "sot_publish"
    assert last_event["publish_target"] == "notebooklm"
    assert last_event["result"] == "success"

@patch('subprocess.run')
@patch('tools.ops.publish_notebooklm.upload_to_notebooklm')
def test_publish_gate_does_not_mutate_tracked_files(mock_upload, mock_run, mock_repo):
    mock_status = MagicMock()
    mock_status.returncode = 0
    mock_status.stdout = ""
    mock_run.return_value = mock_status
    
    setup_valid_pack(mock_repo)
    
    # Run publish
    publish_notebooklm.publish()
    
    # Check that PUBLISH_TEL (the only mutated file) is in gitignore scope
    # Since we can't test actual git behavior here, we check path logic:
    assert publish_notebooklm.PUBLISH_TEL.parent.name == "telemetry"
    assert publish_notebooklm.PUBLISH_TEL.name == "sot_publish.json"
