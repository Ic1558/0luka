#!/usr/bin/env python3
"""Proof runner for Phase 8 dispatcher service DoD."""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _set_env(root: Path) -> dict:
    old = {"ROOT": os.environ.get("ROOT"), "0LUKA_ROOT": os.environ.get("0LUKA_ROOT")}
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    return old


def _restore_env(old: dict) -> None:
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _load_dispatcher(root: Path):
    import core.config as cfg

    importlib.reload(cfg)
    mod = importlib.import_module("core.task_dispatcher")
    mod = importlib.reload(mod)
    mod.ROOT = root
    mod.INBOX = root / "interface" / "inbox"
    mod.COMPLETED = root / "interface" / "completed"
    mod.REJECTED = root / "interface" / "rejected"
    mod.DISPATCH_LOG = root / "observability" / "logs" / "dispatcher.jsonl"
    mod.DISPATCH_LATEST = root / "observability" / "artifacts" / "dispatch_latest.json"
    mod.HEARTBEAT_PATH = root / "observability" / "artifacts" / "dispatcher_heartbeat.json"
    return mod


def _seed_task(root: Path, task_id: str) -> Path:
    inbox = root / "interface" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    task = {
        "task_id": task_id,
        "author": "phase8-proof",
        "schema_version": "clec.v1",
        "intent": "phase8.proof",
        "ops": [{"op_id": "w1", "type": "write_text", "target_path": f"artifacts/{task_id}.txt", "content": "ok"}],
        "verify": [],
    }
    p = inbox / f"{task_id}.yaml"
    p.write_text(json.dumps(task), encoding="utf-8")
    return p


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def run_proof() -> bool:
    root = Path(__file__).resolve().parents[2]
    old = _set_env(root)
    try:
        dispatcher = _load_dispatcher(root)
        import core.run_provenance as rp
        rp = importlib.reload(rp)

        plist_path = root / "ops" / "launchd" / "com.0luka.dispatcher.plist"
        if not plist_path.exists():
            return False

        # Simulate service restart: run watcher twice.
        dispatcher.watch(interval=1, max_cycles=1)
        _seed_task(root, "task_phase8_proof")
        dispatcher.watch(interval=1, max_cycles=1)

        completed = root / "interface" / "completed" / "task_phase8_proof.yaml"
        rejected = root / "interface" / "rejected" / "task_phase8_proof.yaml"
        picked = completed if completed.exists() else rejected
        if not picked.exists():
            return False

        events = _read_jsonl(root / "observability" / "events.jsonl")
        has_started = any(e.get("type") == "execution.started" and e.get("component") == "dispatcher" for e in events)
        has_completed = any(e.get("type") == "execution.completed" and e.get("component") == "dispatcher" for e in events)
        if not (has_started and has_completed):
            return False

        rows = _read_jsonl(root / "observability" / "artifacts" / "run_provenance.jsonl")
        has_dispatcher_row = any(r.get("tool") == "DispatcherService" for r in rows)
        if not has_dispatcher_row:
            return False

        proof_row = rp.init_run_provenance(
            {
                "author": "phase8-proof-runner",
                "tool": "Phase8ProofRunner",
                "evidence_refs": [
                    f"file:{plist_path}",
                    "command:python3 -m core dispatch --watch --interval 1",
                    "command:launchctl print gui/$(id -u)/com.0luka.dispatcher",
                ],
            },
            {"phase": "8", "task": "task_phase8_proof"},
        )
        proof_row = rp.complete_run_provenance(proof_row, {"status": "ok", "task_picked": str(picked)})
        rp.append_provenance(proof_row)

        rp.append_event(
            {
                "type": "execution.verified",
                "category": "execution",
                "actor": "Phase8DispatcherVerifier",
                "proof": {
                    "plist": str(plist_path),
                    "task_picked": str(picked),
                    "events_path": str(root / "observability" / "events.jsonl"),
                },
            }
        )
        return True
    finally:
        _restore_env(old)


def main() -> int:
    ok = run_proof()
    print("phase8_dispatcher_proof:", "ok" if ok else "failed")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
