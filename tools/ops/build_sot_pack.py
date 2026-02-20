#!/usr/bin/env python3
"""
builder: Atomic Internal SOT Pack Builder (WO-14A PR-1)
"""
import os
import subprocess
import json
import hashlib
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SOT_PACKS_DIR = ROOT / "observability" / "artifacts" / "sot_packs"
STAGING_BASE = SOT_PACKS_DIR / "staging"
BUILD_LOCK = SOT_PACKS_DIR / ".build_lock"
FEED_PATH = ROOT / "observability" / "logs" / "activity_feed.jsonl"
SOT_DOC = ROOT / "0luka.md"
SNAP_DIR = ROOT / "observability" / "artifacts" / "snapshots"
CATALOG = ROOT / "core_brain" / "ops" / "catalog_lookup.zsh"

def fail(msg: str) -> None:
    print(f"FATAL: {msg}")
    exit(1)

def run_cmd(cmd: list[str]) -> str:
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if res.returncode != 0:
        fail(f"Command failed: {' '.join(cmd)}\n{res.stderr}")
    return res.stdout.strip()

def check_preconditions() -> str:
    # 1. Clean Git Tree
    status = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
    if status.returncode != 0:
        fail("Failed to run git status")
    if status.stdout.strip():
        fail("Git tree is dirty! Aborting.")
        
    # 2. Seal Proof Chain Validation
    head_sha = run_cmd(["git", "rev-parse", "HEAD"])
    
    feed_sha = None
    if FEED_PATH.exists():
        with open(FEED_PATH, "r") as f:
            lines = f.read().strip().split("\n")
        # Find latest verified event containing git_head, or allow if nothing enforces it yet.
        for line in reversed(lines):
            if not line.strip(): continue
            try:
                ev = json.loads(line)
                if ev.get("action") == "verified" and "git_head" in ev:
                    feed_sha = ev["git_head"]
                    break
            except:
                pass
                
    if feed_sha and not head_sha.startswith(feed_sha):
        fail(f"Seal Proof Chain Mismatch! HEAD={head_sha[:7]} but activity_feed verified commit={feed_sha[:7]}")
        
    return head_sha

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def get_latest_snapshot() -> Path:
    if not SNAP_DIR.exists():
        fail(f"Snapshot directory missing: {SNAP_DIR}")
    snaps = list(SNAP_DIR.glob("*_snapshot.md"))
    if not snaps:
        fail("No snapshots found")
    snaps.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return snaps[0]

def build_pack(head_sha: str):
    SOT_PACKS_DIR.mkdir(parents=True, exist_ok=True)
    STAGING_BASE.mkdir(parents=True, exist_ok=True)
    
    if BUILD_LOCK.exists():
        fail(f"Anti-Race Guard: Build lock file exists: {BUILD_LOCK}")
        
    BUILD_LOCK.touch()
    
    try:
        now = datetime.now(timezone.utc)
        ts_utc = now.strftime("%Y%m%dT%H%M%SZ")
        pack_name = f"{ts_utc}_{head_sha[:7]}"
        pack_dir = STAGING_BASE / pack_name
        pack_dir.mkdir(parents=True, exist_ok=False)
        
        # Collect artifacts
        latest_snap = get_latest_snapshot()
        files = [SOT_DOC, CATALOG, latest_snap]
        
        for f in files:
            if not f.exists():
                fail(f"Artifact missing: {f}")
            shutil.copy2(f, pack_dir / f.name)
            
        # Hashes and Manifest
        sot_sha = sha256_file(pack_dir / SOT_DOC.name)
        
        manifest = {
            "git_head": head_sha,
            "sot_sha256": sot_sha,
            "built_at_utc": ts_utc,
            "builder_version": "14A.1"
        }
        
        # Calculate file hashes
        hashes = {}
        for item in pack_dir.iterdir():
            if item.is_file() and item.name not in ("manifest.json", "sha256sums.txt"):
                hashes[item.name] = sha256_file(item)
                
        # Deterministic Pack Hash
        pack_sha = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
        manifest["pack_sha256"] = pack_sha
        
        with open(pack_dir / "manifest.json", "w") as f:
            json.dump(manifest, f, indent=2)
            
        with open(pack_dir / "sha256sums.txt", "w") as f:
            f.write(f"{pack_sha}  [PACK_SHA256]\n")
            f.write(f"{sot_sha}  {SOT_DOC.name}\n")
            for name, file_sha in sorted(hashes.items()):
                f.write(f"{file_sha}  {name}\n")
                
        # Validate manifest
        with open(pack_dir / "manifest.json") as f:
            test_manifest = json.load(f)
        if test_manifest["pack_sha256"] != pack_sha:
            fail("Integrity check failed on manifest")
            
        # Atomic Promote
        target_dir = SOT_PACKS_DIR / pack_name
        os.rename(str(pack_dir), str(target_dir))
        
        latest_link = SOT_PACKS_DIR / "latest"
        tmp_link = SOT_PACKS_DIR / "latest.tmp"
        if tmp_link.exists():
            tmp_link.unlink()
        
        # Use relative symlink
        os.symlink(pack_name, tmp_link) 
        os.rename(tmp_link, latest_link)
        
        # Emit seal event
        run_id = uuid.uuid4().hex
        event = {
            "ts_utc": ts_utc,
            "ts_epoch_ms": int(now.timestamp() * 1000),
            "phase_id": "PHASE_14",
            "action": "sot_seal",
            "git_head": head_sha,
            "sot_sha256": sot_sha,
            "pack_sha256": pack_sha,
            "run_id": run_id,
            "tool": "build_sot_pack",
            "emit_mode": "runtime_auto",
            "verifier_mode": "operational_proof"
        }
        
        with open(FEED_PATH, "a") as f:
            f.write(json.dumps(event) + "\n")
            
        print(f"SOT Pack atomically built: {pack_name}")
        
    finally:
        if BUILD_LOCK.exists():
            BUILD_LOCK.unlink()

if __name__ == "__main__":
    head = check_preconditions()
    build_pack(head)
