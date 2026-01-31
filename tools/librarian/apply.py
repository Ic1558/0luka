#!/usr/bin/env python3
# tools/librarian/apply.py
# Librarian Apply — Execute move operations from pending.yaml (Approved v1)

import os
import sys
import shutil
from pathlib import Path

from tools.librarian.utils import now_utc_iso, file_checksum, compute_move_id, read_yaml, write_yaml, short_hash, write_json
from tools.librarian.logger import log_event
from tools.librarian.scoring import PASS_THRESHOLD, evaluate_action

def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent

ROOT = Path(os.environ.get("ROOT", _repo_root())).resolve()
STATE_DIR = ROOT / "state"
# Approved v1 Standard: state/librarian/pending.yaml
PENDING_FILE_DEFAULT = STATE_DIR / "librarian" / "pending.yaml"
AUDIT_FILE = STATE_DIR / "recent_changes.jsonl"
CURRENT_SYSTEM_FILE = STATE_DIR / "current_system.json"

def check_core_safety(paths: list) -> tuple[bool, list]:
    """Check if any path touches core (Approved v1)."""
    forbidden = ["core/", "core_brain/", "core_brain/governance/"]
    violations = [p for p in paths if any(f in p for f in forbidden)]
    return len(violations) == 0, violations

def _assert_ts_utc(ts: str) -> None:
    """Validate UTC timestamp format (Approved v1)."""
    import re
    if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts):
        raise SystemExit(f"Invalid ts_utc format (Approved v1): {ts}")

def _append_audit(entry: dict) -> None:
    """Write structured entry to audit log."""
    AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_FILE.open("a", encoding="utf-8") as f:
        import json
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def main() -> int:
    """Librarian Apply: Execute moves from pending.yaml according to policy."""
    
    # Preflight: PyYAML required (Approved v1) via utils.py import check
    try:
        import yaml  # noqa: F401
    except ImportError:
        raise SystemExit("Missing dependency: PyYAML is required. Install: pip install pyyaml")
    
    # Override pending file via CLI argument if provided
    pending_path = PENDING_FILE_DEFAULT
    if len(sys.argv) > 1:
        pending_path = (ROOT / sys.argv[1]).resolve()

    ts = now_utc_iso()
    
    if not pending_path.exists():
        log_event("apply", {"ok": 0, "noop": 1, "error": 1, "note": f"no_pending_file: {pending_path}"})
        return 1
    
    pending = read_yaml(pending_path)
    conflict_policy = pending.get("conflict_policy", "error")
    # Approved v1: We support both 'moves' and 'items' for flexibility, but 'moves' is preferred.
    moves = pending.get("moves", pending.get("items", []))
    
    safe = True
    violations = []
    noop_count = 0
    result = None

    if not moves:
        log_event("apply", {"ok": 0, "noop": 1, "error": 0, "note": "no_moves_in_pending"})
    else:
        for item in moves:
            src_rel = item.get("src_path")
            dst_rel = item.get("dst_path")
            _assert_ts_utc(item.get("ts_utc", ""))
            
            src = (ROOT / src_rel).resolve() if src_rel else None
            dst = (ROOT / dst_rel).resolve() if dst_rel else None
            
            if not src:
                noop_count += 1
                violations.append("src_missing")
                continue
            
            if not dst:
                noop_count += 1
                violations.append("dst_missing")
                continue
            
            safe_check, path_violations = check_core_safety([str(src), str(dst)])
            if not safe_check:
                safe = False
                violations.extend(path_violations)
            
            action = {
                "src_path": src_rel,
                "dst_path": dst_rel,
                "dst_exists": dst.exists(),
                "ts_utc": ts,
                "action_type": "move",
                "conflict_policy": conflict_policy
            }
            
            result = evaluate_action(action)
            
            if result["score"] >= PASS_THRESHOLD:
                if dst.exists():
                    same = file_checksum(src) == file_checksum(dst)
                    if same:
                        noop_count += 1
                        _append_audit({
                            "ts_utc": ts,
                            "event": "librarian_action",
                            "action_type": "move",
                            "move_id": result.get("move_id", ""),
                            "score": result["score"],
                            "breakdown": result.get("breakdown", {}),
                            "gate": result["gate"],
                            "reason": "already_present_same_checksum",
                            "src_path": src_rel,
                            "dst_path": dst_rel,
                            "conflict_policy": conflict_policy
                        })
                    else:
                        if conflict_policy == "error":
                            noop_count += 1
                            violations.append("collision_error_policy_blocked")
                        elif conflict_policy == "rename_with_hash":
                            dst_stem = dst.stem
                            dst_suffix = dst.suffix
                            short_src = short_hash(file_checksum(src))
                            new_name = f"{dst_stem}__dup_{short_src}{dst_suffix}"
                            new_dst = dst.parent / new_name
                            shutil.move(str(dst), str(new_dst))
                            _append_audit({
                                "ts_utc": ts,
                                "event": "librarian_action",
                                "action_type": "move",
                                "move_id": result.get("move_id", ""),
                                "score": result["score"],
                                "breakdown": result.get("breakdown", {}),
                                "gate": result["gate"],
                                "reason": "collision_resolved_with_hash",
                                "src_path": src_rel,
                                "dst_path": str(new_dst.relative_to(ROOT)),
                                "conflict_policy": conflict_policy
                            })
                        else:
                            violations.append(f"unknown_conflict_policy:{conflict_policy}")
                else:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(src), str(dst))
                    _append_audit({
                        "ts_utc": ts,
                        "event": "librarian_action",
                        "action_type": "move",
                        "move_id": result.get("move_id", ""),
                        "score": result["score"],
                        "breakdown": result.get("breakdown", {}),
                        "gate": result["gate"],
                        "reason": "",
                        "src_path": src_rel,
                        "dst_path": dst_rel,
                        "conflict_policy": conflict_policy
                    })

    # Update current_system.json (Maintain traceability)
    try:
        current_system = read_yaml(CURRENT_SYSTEM_FILE) if CURRENT_SYSTEM_FILE.exists() else {}
        current_system.setdefault("ts_utc", ts)
        
        status_update = {
            "last_run_ts_utc": ts,
            "last_gate": result.get("gate", "OK") if result else "OK"
        }
        if result:
            status_update["last_score"] = result["score"]
            
        librarian_status = current_system.get("librarian", {})
        librarian_status.update(status_update)
        current_system["librarian"] = librarian_status
        write_json(CURRENT_SYSTEM_FILE, current_system)
    except Exception:
        pass
    
    log_event("apply", {"ok": 1 if (safe and not violations) else 0, "noop": noop_count > 0, "error": len(violations)})
    return 0 if (safe and not violations) else 1

if __name__ == "__main__":
    sys.exit(main())
