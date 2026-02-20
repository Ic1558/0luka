import os
import sys
import json
import pytest
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure tools.ops.build_sot_pack is importable
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import tools.ops.build_sot_pack as build_sot_pack

@pytest.fixture
def mock_repo(tmp_path):
    # mock roots
    orig_root = build_sot_pack.ROOT
    orig_sot = build_sot_pack.SOT_PACKS_DIR
    orig_feed = build_sot_pack.FEED_PATH
    orig_snap = build_sot_pack.SNAP_DIR
    orig_doc = build_sot_pack.SOT_DOC
    orig_cat = build_sot_pack.CATALOG
    orig_staging = build_sot_pack.STAGING_BASE
    orig_lock = build_sot_pack.BUILD_LOCK
    
    test_root = tmp_path
    
    build_sot_pack.ROOT = test_root
    build_sot_pack.SOT_PACKS_DIR = test_root / "sot_packs"
    build_sot_pack.STAGING_BASE = build_sot_pack.SOT_PACKS_DIR / "staging"
    build_sot_pack.BUILD_LOCK = build_sot_pack.SOT_PACKS_DIR / ".build_lock"
    build_sot_pack.FEED_PATH = test_root / "activity_feed.jsonl"
    build_sot_pack.SNAP_DIR = test_root / "snapshots"
    build_sot_pack.SOT_DOC = test_root / "0luka.md"
    build_sot_pack.CATALOG = test_root / "catalog_lookup.zsh"
    
    # create fake dependencies
    build_sot_pack.SNAP_DIR.mkdir()
    (build_sot_pack.SNAP_DIR / "123_snapshot.md").write_text("fake snap")
    build_sot_pack.SOT_DOC.write_text("fake 0luka")
    build_sot_pack.CATALOG.write_text("fake catalog")
    build_sot_pack.FEED_PATH.write_text("")
    
    yield test_root
    
    # restore
    build_sot_pack.ROOT = orig_root
    build_sot_pack.SOT_PACKS_DIR = orig_sot
    build_sot_pack.STAGING_BASE = orig_staging
    build_sot_pack.BUILD_LOCK = orig_lock
    build_sot_pack.FEED_PATH = orig_feed
    build_sot_pack.SNAP_DIR = orig_snap
    build_sot_pack.SOT_DOC = orig_doc
    build_sot_pack.CATALOG = orig_cat


@patch('subprocess.run')
def test_preconditions_dirty_tree(mock_run, mock_repo):
    # Mock dirty tree
    mock_status = MagicMock()
    mock_status.returncode = 0
    mock_status.stdout = " M 0luka.md\n"
    mock_run.return_value = mock_status
    
    with pytest.raises(SystemExit):
        build_sot_pack.check_preconditions()


@patch('subprocess.run')
def test_preconditions_seal_mismatch(mock_run, mock_repo):
    # Mock clean tree
    mock_status = MagicMock()
    mock_status.returncode = 0
    mock_status.stdout = ""
    
    # Mock HEAD
    mock_head = MagicMock()
    mock_head.returncode = 0
    mock_head.stdout = "aaaaaaa\n"
    
    mock_run.side_effect = [mock_status, mock_head]
    
    # Mock feed file with git_head
    build_sot_pack.FEED_PATH.write_text('{"action": "verified", "git_head": "bbbbbbb"}\n')
    
    with pytest.raises(SystemExit):
        build_sot_pack.check_preconditions()


@patch('subprocess.run')
def test_preconditions_clean(mock_run, mock_repo):
    mock_status = MagicMock()
    mock_status.returncode = 0
    mock_status.stdout = ""
    
    mock_head = MagicMock()
    mock_head.returncode = 0
    mock_head.stdout = "aaaaaaa\n"
    
    mock_run.side_effect = [mock_status, mock_head]
    
    # Mock feed file with matching git_head
    build_sot_pack.FEED_PATH.write_text('{"action": "verified", "git_head": "aaaaaaa"}\n')
    
    head = build_sot_pack.check_preconditions()
    assert head == "aaaaaaa"


def test_build_pack_success(mock_repo):
    head_sha = "abcdef0"
    build_sot_pack.build_pack(head_sha)
    
    # Verify latest pointer exists
    latest = build_sot_pack.SOT_PACKS_DIR / "latest"
    assert latest.is_symlink()
    
    pack_name = os.readlink(latest)
    pack_dir = build_sot_pack.SOT_PACKS_DIR / pack_name
    assert pack_dir.exists()
    
    # Verify files inside pack
    assert (pack_dir / "0luka.md").exists()
    assert (pack_dir / "catalog_lookup.zsh").exists()
    assert (pack_dir / "123_snapshot.md").exists()
    assert (pack_dir / "manifest.json").exists()
    assert (pack_dir / "sha256sums.txt").exists()
    
    # Verify manifest
    with open(pack_dir / "manifest.json") as f:
        manifest = json.load(f)
    assert manifest["git_head"] == head_sha
    assert "pack_sha256" in manifest
    assert "sot_sha256" in manifest
    
    # Verify feed emission
    with open(build_sot_pack.FEED_PATH) as f:
        events = f.read().strip().split('\n')
    assert len(events) == 1
    event = json.loads(events[0])
    assert event["action"] == "sot_seal"
    assert event["git_head"] == head_sha
    assert event["pack_sha256"] == manifest["pack_sha256"]

def test_anti_race_guard(mock_repo):
    head_sha = "abcdef0"
    build_sot_pack.SOT_PACKS_DIR.mkdir(parents=True, exist_ok=True)
    build_sot_pack.BUILD_LOCK.touch()
    
    with pytest.raises(SystemExit):
        build_sot_pack.build_pack(head_sha)
