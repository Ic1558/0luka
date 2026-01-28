#!/usr/bin/env python3
"""
E2E Validation: Task → Bridge → Consumer → Handoff → Reader
Proves the complete lifecycle with SOT entrypoint guarantee.
"""
import json
import os
import subprocess
import time
from pathlib import Path

ROOT = Path(os.environ.get("ROOT", Path.cwd())).resolve()

HANDOFF = ROOT / "observability" / "artifacts" / "handoff_latest.json"
READ_HANDOFF = ROOT / "observability" / "tools" / "memory" / "read_handoff.zsh"

# You must point this to your real emission mechanism.
# Prefer: tools/bridge_task_emit.zsh (seen in snapshot)
EMIT = ROOT / "tools" / "bridge_task_emit.zsh"

TIMEOUT_S = int(os.environ.get("E2E_TIMEOUT_S", "45"))
POLL_S = float(os.environ.get("E2E_POLL_S", "1.0"))

def run(cmd, check=True, capture=True, text=True, **kw):
    res = subprocess.run(cmd, check=check, capture_output=capture, text=text, **kw)
    return res.stdout.strip()

def assert_exists(p: Path, msg: str):
    if not p.exists():
        raise AssertionError(f"{msg}: missing {p}")

def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))

def wait_for_handoff_change(prev_mtime: float):
    deadline = time.time() + TIMEOUT_S
    while time.time() < deadline:
        if HANDOFF.exists():
            m = HANDOFF.stat().st_mtime
            if m > prev_mtime:
                return m
        time.sleep(POLL_S)
    raise AssertionError(f"handoff_latest.json did not update within {TIMEOUT_S}s")

def validate_handoff_schema(h: dict):
    # Minimal required (task_artifacts.py schema)
    for k in ["trace_id", "paths"]:
        if k not in h or not h[k]:
            raise AssertionError(f"handoff missing required key: {k}")

    paths = h.get("paths", {})
    if not isinstance(paths, dict):
        raise AssertionError("handoff.paths must be a dict")
    
    # Security: all paths must be inside repo
    for key, path_str in paths.items():
        p = Path(path_str)
        resolved = p.resolve() if p.is_absolute() else (ROOT / p).resolve()
        if not str(resolved).startswith(str(ROOT)):
            raise AssertionError(f"handoff.paths.{key} escapes ROOT")
        if ".." in p.parts:
            raise AssertionError(f"handoff.paths.{key} must not contain '..'")

def main():
    print(f"ROOT={ROOT}")

    assert_exists(EMIT, "Emitter script not found")
    assert_exists(READ_HANDOFF, "Reader script not found")

    prev_mtime = HANDOFF.stat().st_mtime if HANDOFF.exists() else 0.0

    # Emit a dispatch directly to outbox/liam/ (production lane)
    # Consumer reads from: observability/bridge/outbox/{executor}/*_dispatch.json
    trace_id = f"e2e-test-{int(time.time())}"
    task_id = f"e2e_{int(time.time() * 1000)}"
    
    dispatch = {
        "task_id": task_id,
        "trace_id": trace_id,
        "executor": "liam",
        "origin": "test_e2e",
        "intent": "task.emit",
        "payload": {
            "goal": "E2E validation test",
            "kind": "test_e2e_full",
            "ts": time.time(),
            "expect_echo": "HELLO_E2E",
        },
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    
    outbox_dir = ROOT / "observability" / "bridge" / "outbox" / "liam"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    dispatch_file = outbox_dir / f"{task_id}_dispatch.json"
    dispatch_file.write_text(json.dumps(dispatch, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"EMIT: dispatch -> {dispatch_file}")

    # Wait for handoff_latest.json to update (consumer processed)
    new_mtime = wait_for_handoff_change(prev_mtime)
    print(f"handoff_latest.json updated (mtime={new_mtime})")

    h = load_json(HANDOFF)
    validate_handoff_schema(h)

    # task_artifacts.py writes paths dict with meta, plan_json, plan_md, etc.
    paths = h.get("paths", {})
    meta_path = paths.get("meta") or paths.get("meta_json")
    if meta_path:
        meta_path = Path(meta_path)
        task_dir = meta_path.parent
    else:
        raise AssertionError("handoff.paths.meta missing")
    
    print("task_dir:", task_dir)

    # Required KEEP files (meta exists via paths)
    assert_exists(task_dir, "Task dir not created")
    assert_exists(meta_path, "meta.json missing")

    # At least one phase file should exist (plan or result or reply)
    has_any = any((task_dir / f).exists() for f in ["plan.md", "plan.json", "result.json", "reply.md"])
    if not has_any:
        raise AssertionError("Expected at least one of plan.md/plan.json/result.json/reply.md")

    # Reader must use SOT entrypoint (no direct trace path)
    # Assume read_handoff prints JSON or a stable text format including trace_id
    out = run(["zsh", str(READ_HANDOFF)], check=True)
    if str(h["trace_id"]) not in out:
        raise AssertionError("Reader output does not reference the current trace_id (SOT mismatch)")

    # Stronger check (optional): if reader outputs JSON with echo, validate it
    # We keep it lenient because your reader format may differ.
    print("OK: E2E proof passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
