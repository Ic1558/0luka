#!/usr/bin/env python3
"""
publish: External Publish Gate (WO-14A PR-2 Class B)
"""
import os
import subprocess
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SOT_PACKS_DIR = ROOT / "observability" / "artifacts" / "sot_packs"
FEED_PATH = ROOT / "observability" / "logs" / "activity_feed.jsonl"
PUBLISH_TEL = ROOT / "observability" / "telemetry" / "sot_publish.json"
SYNC_LOCK = SOT_PACKS_DIR / "latest" / ".sync_lock"

def fail(msg: str) -> None:
    print(f"FATAL: {msg}")
    exit(1)

def run_cmd(cmd: list[str]) -> str:
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        fail(f"Command failed: {' '.join(cmd)}\n{res.stderr}")
    return res.stdout.strip()

def check_gates() -> dict:
    # Check tree is clean
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
    if status.returncode != 0:
        fail("git status failed")
    if status.stdout.strip():
        fail(f"Git tree is dirty! Cannot publish uncommitted state.\n{status.stdout}")

    # Inspect latest pack
    latest_dir = SOT_PACKS_DIR / "latest"
    if not latest_dir.exists() or not latest_dir.is_symlink():
        fail(f"Latest SOT pack linked dir missing at {latest_dir}")
        
    manifest_path = latest_dir / "manifest.json"
    if not manifest_path.exists():
        fail("SOT pack missing manifest.json")
        
    with open(manifest_path) as f:
        manifest = json.load(f)
        
    pack_sha = manifest.get("pack_sha256")
    git_head = manifest.get("git_head")
    if not pack_sha or not git_head:
        fail("Invalid manifest: missing pack_sha256 or git_head")
        
    # Read last sot_seal from feed
    feed_pack_sha = None
    seal_run_id = None
    if FEED_PATH.exists():
        with open(FEED_PATH) as f:
            lines = f.read().strip().split("\n")
        
        for line in reversed(lines):
            try:
                ev = json.loads(line)
                if ev.get("action") == "sot_seal":
                    feed_pack_sha = ev.get("pack_sha256")
                    seal_run_id = ev.get("run_id")
                    break
            except Exception:
                pass
                
    if not feed_pack_sha:
        fail("No 'sot_seal' event found in activity_feed.jsonl. Cannot publish.")
        
    if feed_pack_sha != pack_sha:
        fail(f"Pack hash mismatch! Latest SEAL event={feed_pack_sha} vs Pack manifest={pack_sha}")
        
    return {
        "pack_dir": latest_dir,
        "pack_sha": pack_sha,
        "sot_sha": manifest.get("sot_sha256"),
        "git_head": git_head,
        "seal_run_id": seal_run_id
    }

def upload_to_notebooklm(pack_dir: Path):
    """
    Mock integration point for NotebookLM MCP.
    In a real scenario, this would execute MCP commands or `0luka_to_notebook.zsh` behavior internally.
    But as per spec, we just mock the exit here to signify the gate worked.
    """
    print(f"Deploying {pack_dir} to NotebookLM MCP... [MOCKED SUCCESS]")

def publish():
    SYNC_LOCK.parent.mkdir(parents=True, exist_ok=True)
    try:
        if SYNC_LOCK.exists():
            fail(f"Concurrency Lock! Publish operation already in progress {SYNC_LOCK}")
            
        SYNC_LOCK.touch()
        
        gates = check_gates()
        
        # External Egress Egress
        upload_to_notebooklm(gates["pack_dir"])
        
        now = datetime.now(timezone.utc)
        ts_utc = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Record to metadata file
        tel = {
            "last_published_utc": ts_utc,
            "git_head": gates["git_head"],
            "pack_sha256": gates["pack_sha"],
            "seal_run_id": gates["seal_run_id"],
            "target": "notebooklm"
        }
        PUBLISH_TEL.parent.mkdir(parents=True, exist_ok=True)
        with open(PUBLISH_TEL, "w") as f:
            json.dump(tel, f, indent=2)
            
        # Emit feed event
        event = {
            "ts_utc": ts_utc,
            "ts_epoch_ms": int(now.timestamp() * 1000),
            "phase_id": "PHASE_14",
            "action": "sot_publish",
            "sot_sha256": gates["sot_sha"],
            "pack_sha256": gates["pack_sha"],
            "seal_run_id": gates["seal_run_id"],
            "publish_target": "notebooklm",
            "run_id": uuid.uuid4().hex,
            "tool": "publish_notebooklm",
            "emit_mode": "runtime_auto",
            "verifier_mode": "operational_proof",
            "result": "success"
        }
        
        with open(FEED_PATH, "a") as f:
            f.write(json.dumps(event) + "\n")
            
        print("Publish successful.")
        
    finally:
        if SYNC_LOCK.exists():
            SYNC_LOCK.unlink()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NotebookLM MCP External Publish Gate")
    parser.add_argument("--publish", action="store_true", required=True, help="Explicit trigger required to execute publish.")
    args = parser.parse_args()
    
    publish()
