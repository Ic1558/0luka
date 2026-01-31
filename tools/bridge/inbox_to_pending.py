from __future__ import annotations

import json
import os
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# PyYAML strict dependency (aligned with Librarian R2)
try:
    import yaml  # type: ignore
except Exception:
    print("[FATAL] PyYAML is required. Install: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

ISOZ_SUFFIX = "Z"

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def is_isoz(s: str) -> bool:
    return isinstance(s, str) and s.endswith(ISOZ_SUFFIX) and "T" in s

def load_any(path: Path) -> dict[str, Any]:
    txt = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in (".yaml", ".yml"):
        data = yaml.safe_load(txt) or {}
    elif path.suffix.lower() == ".json":
        data = json.loads(txt)
    else:
        # try yaml then json
        try:
            data = yaml.safe_load(txt) or {}
        except Exception:
            data = json.loads(txt)
    if not isinstance(data, dict):
        raise ValueError("task root must be an object")
    return data

def atomic_write_text(path: Path, content: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)

def repo_rel_guard(p: str) -> None:
    # Forensic rule: tasks must be repo-relative, never absolute
    if not isinstance(p, str) or not p.strip():
        raise ValueError("path is empty")
    if p.startswith("/") or p.startswith("~") or ":\\" in p or p.startswith("\\\\"):
        raise ValueError(f"absolute/tilde path forbidden: {p}")
    if ".." in Path(p).parts:
        raise ValueError(f"path traversal forbidden: {p}")

@dataclass
class TaskResult:
    ok: bool
    task_id: str
    ts_utc: str
    intent: str
    pending_appended: int
    reason: str = ""

def normalize_pending(pending: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(pending, dict):
        pending = {}
    conflict_policy = pending.get("conflict_policy", "error")
    items = pending.get("items", [])
    if not isinstance(items, list):
        items = []
    return {"conflict_policy": conflict_policy, "items": items}

def main() -> int:
    if len(sys.argv) != 5:
        print("Usage: inbox_to_pending.py <ROOT> <inbox_new> <inbox_processing> <pending_yaml>", file=sys.stderr)
        return 2

    root = Path(sys.argv[1]).resolve()
    inbox_new = Path(sys.argv[2]).resolve()
    inbox_processing = Path(sys.argv[3]).resolve()
    pending_yaml = Path(sys.argv[4]).resolve()

    inbox_done = (root / "state/inbox/done").resolve()
    inbox_rejected = (root / "state/inbox/rejected").resolve()
    inbox_done.mkdir(parents=True, exist_ok=True)
    inbox_rejected.mkdir(parents=True, exist_ok=True)
    pending_yaml.parent.mkdir(parents=True, exist_ok=True)

    # scan tasks
    task_files = sorted([p for p in inbox_new.glob("*") if p.is_file()])
    ts = now_utc_iso()

    processed = 0
    rejected = 0
    appended_total = 0

    # load pending once
    if pending_yaml.exists():
        pending = normalize_pending(yaml.safe_load(pending_yaml.read_text(encoding="utf-8", errors="replace")) or {})
    else:
        pending = normalize_pending({})

    for tf in task_files:
        processed += 1
        # move to processing first (atomic claim)
        proc_path = inbox_processing / tf.name
        inbox_processing.mkdir(parents=True, exist_ok=True)
        try:
            tf.replace(proc_path)
        except Exception as e:
            rejected += 1
            (inbox_rejected / (tf.name + ".claim_error.txt")).write_text(str(e), encoding="utf-8")
            continue

        try:
            task = load_any(proc_path)

            task_id = str(task.get("task_id", "")).strip()
            intent = str(task.get("intent", "")).strip()
            tts = task.get("ts_utc") or task.get("ts") or ""
            tts = str(tts).strip()

            if not task_id:
                raise ValueError("missing task_id")
            if not intent:
                raise ValueError("missing intent")
            if tts and not is_isoz(tts):
                raise ValueError(f"invalid ts_utc: {tts}")
            if not tts:
                tts = ts

            if intent == "noop":
                # no pending write, just mark done
                res = TaskResult(ok=True, task_id=task_id, ts_utc=tts, intent=intent, pending_appended=0)
                out = yaml.safe_dump(res.__dict__, sort_keys=False, allow_unicode=True)
                (inbox_done / (proc_path.name + ".result.yaml")).write_text(out, encoding="utf-8")
                proc_path.replace(inbox_done / proc_path.name)
                continue

            if intent != "librarian_move":
                raise ValueError(f"unknown intent: {intent}")

            payload = task.get("payload") or {}
            if not isinstance(payload, dict):
                raise ValueError("payload must be an object")

            conflict_policy = payload.get("conflict_policy") or pending.get("conflict_policy", "error")
            if conflict_policy not in ("error", "rename_with_hash"):
                raise ValueError(f"invalid conflict_policy: {conflict_policy}")
            pending["conflict_policy"] = conflict_policy

            moves = payload.get("moves") or []
            if not isinstance(moves, list) or not moves:
                raise ValueError("payload.moves must be a non-empty list")

            appended = 0
            for m in moves:
                if not isinstance(m, dict):
                    raise ValueError("each move must be an object")
                src = str(m.get("src", "")).strip()
                dst = str(m.get("dst", "")).strip()
                mts = str(m.get("ts_utc", "")).strip() or tts

                repo_rel_guard(src)
                repo_rel_guard(dst)
                if not is_isoz(mts):
                    raise ValueError(f"invalid move ts_utc: {mts}")

                entry = {"src_path": src, "dst_path": dst, "ts_utc": mts}

                # light dedupe: exact triple match
                if entry in pending["items"]:
                    continue

                pending["items"].append(entry)
                appended += 1

            appended_total += appended

            res = TaskResult(ok=True, task_id=task_id, ts_utc=tts, intent=intent, pending_appended=appended)
            out = yaml.safe_dump(res.__dict__, sort_keys=False, allow_unicode=True)
            (inbox_done / (proc_path.name + ".result.yaml")).write_text(out, encoding="utf-8")
            proc_path.replace(inbox_done / proc_path.name)

        except Exception as e:
            rejected += 1
            reason = f"{type(e).__name__}: {e}"
            (inbox_rejected / (proc_path.name + ".reason.txt")).write_text(reason, encoding="utf-8")
            # keep original task for forensic review
            try:
                proc_path.replace(inbox_rejected / proc_path.name)
            except Exception:
                pass

    # write pending atomically only if changed
    # always write normalized for stability
    pending_out = yaml.safe_dump(pending, sort_keys=False, allow_unicode=True)
    atomic_write_text(pending_yaml, pending_out)

    # summary line (grep-friendly)
    print(f"[{ts}] inbox_bridge finished | exit=0 processed={processed} rejected={rejected} pending_appended={appended_total}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
