import hashlib
import os

def sha256_file(path):
    """Compute sha256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def path_under_roots(path, roots):
    path = os.path.abspath(os.path.expanduser(path))
    for root in roots:
        root = os.path.abspath(os.path.expanduser(root))
        if path.startswith(root):
            return True
    return False

def gate_fs_purity(task_spec, result_bundle):
    """
    Pass if:
      - every observed write/delete is within task_spec.scope.allowed_roots
      - every observed write path is declared in artifacts.outputs
    """
    allowed_roots = task_spec["scope"]["allowed_roots"]
    declared_outputs = {os.path.abspath(os.path.expanduser(o["path"])) for o in task_spec["artifacts"].get("outputs", [])}

    writes_raw = result_bundle.get("gates", {}).get("observed_fs_writes", [])
    writes = [w["path"] if isinstance(w, dict) else w for w in writes_raw]
    deletes_raw = result_bundle.get("artifacts", {}).get("deleted", [])
    deletes = [d["path"] if isinstance(d, dict) else d for d in deletes_raw]

    violations = []
    for p in writes + deletes:
        if not isinstance(p, str): 
            violations.append(("invalid_type", str(p)))
            continue
        if not path_under_roots(p, allowed_roots):
            violations.append(("outside_allowed_roots", p))
    
    for p in writes:
        if not isinstance(p, str): continue
        if os.path.abspath(os.path.expanduser(p)) not in declared_outputs:
            violations.append(("undeclared_write", p))

    ok = (len(violations) == 0)
    return {
      "pass": ok,
      "reason": "ok" if ok else f"fs purity violations: {violations}",
      "evidence": {"violations": violations},
    }

def gate_hash_match(task_spec, result_bundle):
    """
    Pass if:
      - every required output has a matching hash in result_bundle.
    """
    required_outputs = [o for o in task_spec["artifacts"].get("outputs", []) if o.get("required", True)]
    bundle_outputs = {os.path.abspath(os.path.expanduser(o["path"])): o.get("hash") 
                      for o in result_bundle.get("artifacts", {}).get("outputs", [])}

    missing = []
    mismatch = []

    for o in required_outputs:
        path = os.path.abspath(os.path.expanduser(o["path"]))
        h = bundle_outputs.get(path)
        if not h:
            missing.append(path)
            continue
        try:
            actual = sha256_file(path)
            if h != f"sha256:{actual}":
                mismatch.append((path, h, f"sha256:{actual}"))
        except Exception as e:
            mismatch.append((path, str(e)))

    ok = (not missing) and (not mismatch)
    return {
      "pass": ok,
      "reason": "ok" if ok else f"hash issues missing={missing} mismatch={mismatch}",
      "evidence": {"missing": missing, "mismatch": mismatch},
    }

def gate_proc_clean(task_spec, result_bundle):
    """
    Pass if:
      - spawn is followed according to capabilities.
    """
    caps = task_spec.get("capabilities", {}).get("process", {})
    spawn_allowed = bool(caps.get("spawn", False))
    observed = result_bundle.get("gates", {}).get("observed_processes", [])

    violations = []
    if not spawn_allowed and observed:
        violations.append(("spawn_not_allowed", [p.get("cmd") for p in observed]))

    for p in observed:
        if not p.get("ended_clean", False):
            violations.append(("orphan_or_dirty", p))

    ok = (len(violations) == 0)
    return {
      "pass": ok,
      "reason": "ok" if ok else f"proc cleanliness violations: {violations}",
      "evidence": {"observed": observed, "violations": violations},
    }
