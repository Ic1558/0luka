import os
import subprocess
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

# NotebookLM MCP Integration
from notebooklm_mcp.api_client import NotebookLMClient
from notebooklm_mcp.auth import load_cached_tokens

ROOT = Path(__file__).resolve().parent.parent.parent
SOT_PACKS_DIR = ROOT / "observability" / "artifacts" / "sot_packs"
FEED_PATH = ROOT / "observability" / "logs" / "activity_feed.jsonl"
PUBLISH_TEL = ROOT / "observability" / "telemetry" / "sot_publish.json"
SYNC_LOCK = SOT_PACKS_DIR / "latest" / ".sync_lock"

NOTEBOOK_ID = "a3c7bcdd-d78b-422d-b3e2-e143cb91588e"

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
        # Special case: .gitignore change for repos/qs is allowed if it was just committed, 
        # but build_sot_pack.py usually handles this.
        # We enforce a strictly clean tree for publish.
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
    Real implementation for NotebookLM Publish.
    Replace stale sources with fresh content from sealed pack.
    """
    print(f"Initializing NotebookLM client for notebook {NOTEBOOK_ID}...")
    tokens = load_cached_tokens()
    if not tokens:
        raise Exception("No cached NotebookLM tokens found. Run 'notebooklm-mcp-auth' first.")
        
    client = NotebookLMClient(
        cookies=tokens.cookies, 
        csrf_token=tokens.csrf_token, 
        session_id=tokens.session_id
    )
    
    # Identify files in pack
    sot_file = pack_dir / "0luka.md"
    catalog_file = pack_dir / "catalog_lookup.zsh"
    snapshot_file = next(pack_dir.glob("*_snapshot.md"), None)
    
    if not sot_file.exists(): raise Exception(f"Missing {sot_file}")
    if not catalog_file.exists(): raise Exception(f"Missing {catalog_file}")
    if not snapshot_file: raise Exception("Missing snapshot file in pack")
    
    targets = [
        # TITLE CONTRACT: These fixed titles are used to identify mirrored SOT content.
        # Renaming these in NotebookLM will break the replacement logic and cause duplicates.
        {"title": "0luka [SOT]", "path": sot_file},
        {"title": "Catalog Index", "path": catalog_file},
        {"title": "System Snapshot", "path": snapshot_file}
    ]
    
    print("Fetching existing remote sources...")
    remote_sources = client.get_notebook_sources_with_types(NOTEBOOK_ID)
    target_titles = [t["title"] for t in targets]
    stale_source_ids = [s["id"] for s in remote_sources if s["title"] in target_titles]
    
    # 1. Upload Fresh Context FIRST (Maintain Availability)
    print("Uploading fresh sources...")
    new_source_ids = []
    for target in targets:
        content = target["path"].read_text()
        print(f" - Uploading '{target['title']}'...")
        res = client.add_text_source(NOTEBOOK_ID, content, target["title"])
        if not res or "id" not in res:
            if isinstance(res, dict) and res.get("status") == "timeout":
                print(f"   WARNING: Upload of {target['title']} timed out but may succeed on backend.")
            else:
                raise Exception(f"Failed to upload {target['title']}: {res}")
        else:
            print(f"   Success: {res['id']}")
            new_source_ids.append(res["id"])
            
    # 2. Cleanup Stale Context ONLY AFTER SUCCESS (Minimize Mirror Downtime)
    if stale_source_ids:
        print(f"Cleaning up {len(stale_source_ids)} stale sources...")
        for src_id in stale_source_ids:
            try:
                client.delete_source(src_id)
            except Exception as e:
                print(f"   WARNING: Failed to delete stale source {src_id}: {e}")

def record_publish_event(gates: dict, result: str, error: str = None):
    now = datetime.now(timezone.utc)
    ts_utc = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Update telemetry file
    if result == "success":
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
        "result": result
    }
    if error:
        event["error"] = error
        
    with open(FEED_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")

def publish():
    SYNC_LOCK.parent.mkdir(parents=True, exist_ok=True)
    gates = None
    try:
        if SYNC_LOCK.exists():
            fail(f"Concurrency Lock! Publish operation already in progress {SYNC_LOCK}")
            
        SYNC_LOCK.touch()
        
        gates = check_gates()
        
        # External Egress
        upload_to_notebooklm(gates["pack_dir"])
        
        record_publish_event(gates, "success")
        print("Publish successful.")
        
    except Exception as e:
        if gates:
            record_publish_event(gates, "failed", str(e))
        fail(f"Publish process halted: {e}")
        
    finally:
        if SYNC_LOCK.exists():
            SYNC_LOCK.unlink()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NotebookLM MCP External Publish Gate")
    parser.add_argument("--publish", action="store_true", required=True, help="Explicit trigger required to execute publish.")
    args = parser.parse_args()
    
    publish()
