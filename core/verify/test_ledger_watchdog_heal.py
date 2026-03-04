import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WATCHDOG_PY = ROOT / "tools/ops" / "ledger_watchdog.py"

def test_watchdog_heal_creates_dirs_only():
    """--heal flag should create missing runtime log directories and NOT touch ledger files."""
    with tempfile.TemporaryDirectory() as td:
        tmp_root = Path(td).resolve()
        log_dir = tmp_root / "logs"
        assert not log_dir.exists()

        env = os.environ.copy()
        env["LUKA_RUNTIME_ROOT"] = str(tmp_root)

        # USE --no-emit to prevent writing to activity_feed.jsonl
        cmd = [sys.executable, str(WATCHDOG_PY), "--check-epoch", "--heal", "--no-emit", "--json"]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        assert log_dir.exists()
        assert (log_dir / "archive").exists()
        
        # LEDGER SAFETY ASSERTIONS
        assert not (log_dir / "activity_feed.jsonl").exists(), "Should not create feed"
        assert not (log_dir / "epoch_manifest.jsonl").exists(), "Should not create manifest"
        
        report = json.loads(result.stdout)
        assert report["healing_attempted"] is True

def test_watchdog_remediation_integrity_only():
    """Remediation request should be emitted ONLY for integrity failures, not missing files."""
    with tempfile.TemporaryDirectory() as td:
        tmp_root = Path(td).resolve()
        log_dir = tmp_root / "logs"
        log_dir.mkdir()
        
        env = os.environ.copy()
        env["LUKA_RUNTIME_ROOT"] = str(tmp_root)

        # 1. Operational failure (missing file) -> No remediation
        cmd = [sys.executable, str(WATCHDOG_PY), "--check-epoch", "--no-emit", "--json"]
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        report = json.loads(result.stdout)
        assert report["remediation_emitted"] is False
        assert not (log_dir / "remediation_requests.jsonl").exists()

        # 2. Simulated Integrity failure (hash mismatch)
        feed_path = log_dir / "activity_feed.jsonl"
        feed_path.write_text('{"ts_utc": "2026-03-04T00:00:00Z", "action": "ledger_anchor", "prev_hash": "GENESIS", "hash": "bad"}\n', encoding="utf-8")
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        report = json.loads(result.stdout)
        
        assert report["remediation_emitted"] is True
        assert (log_dir / "remediation_requests.jsonl").exists()

def test_watchdog_emitter_no_create_root():
    """Emitter must be best-effort and not create logs directory if root is invalid."""
    with tempfile.TemporaryDirectory() as td:
        tmp_root = Path(td).resolve()
        env = os.environ.copy()
        env["LUKA_RUNTIME_ROOT"] = str(tmp_root)

        # We test the internal function directly to ensure no side-effects
        sys.path.insert(0, str(ROOT))
        from tools.ops.ledger_watchdog import _emit_remediation_request
        path = _emit_remediation_request(tmp_root, {"test": True})
        
        assert path is None, "Emitter should not have created logs directory"
        assert not (tmp_root / "logs").exists()
