from __future__ import annotations
import os, json, hashlib, subprocess
from typing import Dict, Any, Tuple, List

def _expand_path(path: str) -> str:
    if not path:
        return path
    if "ROOT" not in os.environ:
        os.environ["ROOT"] = os.path.expanduser("~/0luka")
    return os.path.expanduser(os.path.expandvars(path))

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def gate_fs_purity(task: Dict[str, Any], allowed_roots: List[str]) -> Tuple[bool, Dict[str, Any]]:
    outs = task.get("artifacts", {}).get("outputs", [])
    bad = []
    expanded_roots = [_expand_path(r) for r in allowed_roots]
    for out in outs:
        p_raw = out.get("path", "")
        p = _expand_path(p_raw)
        if not p or not any(p.startswith(r.rstrip("/") + "/") or p == r.rstrip("/") for r in expanded_roots):
            bad.append(p_raw)
    return (len(bad) == 0), {"bad_paths": bad}

def gate_hash_match(task: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    outs = task.get("artifacts", {}).get("outputs", [])
    mismatched = []
    for out in outs:
        p_raw = out.get("path")
        p = _expand_path(p_raw)
        expect = out.get("sha256")
        if not p or not expect:
            mismatched.append({"path": p_raw, "reason": "missing path/sha256"})
            continue
        if not os.path.exists(p):
            mismatched.append({"path": p_raw, "reason": "missing file"})
            continue
        got = _sha256_file(p)
        if got != expect:
            mismatched.append({"path": p_raw, "expect": expect, "got": got})
    return (len(mismatched) == 0), {"mismatched": mismatched}

def gate_proc_clean(patterns=None) -> Tuple[bool, Dict[str, Any]]:
    # Best-effort: ensure old loopers are not running.
    # HARDENING: Ignore processes involving '02luka' to avoid false positives from legacy parallel systems.
    if patterns is None:
        patterns = ["mary_dispatcher", "shell_watcher", "clc_bridge", "mls_watcher"]
    cmd = "ps aux"
    try:
        out = subprocess.check_output(cmd, shell=True, text=True)
        hits = []
        for line in out.splitlines():
            # If 02luka is in the line, assume it's the external system and ignore it for 0luka Core purity (Clean Room).
            if "/02luka/" in line:
                continue
            if any(p in line for p in patterns) and "grep" not in line:
                hits.append(line)
        return (len(hits) == 0), {"hits": hits}
    except Exception as e:
        return False, {"error": str(e)}
