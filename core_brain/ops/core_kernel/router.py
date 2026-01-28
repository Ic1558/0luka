from __future__ import annotations
import os, sys, json, time
from pathlib import Path

try:
    import yaml  # type: ignore
except Exception as e:
    print("ERROR: missing PyYAML. Install with: python3 -m pip install pyyaml", file=sys.stderr)
    raise

from gates import gate_fs_purity, gate_hash_match, gate_proc_clean

def _normalize_root() -> str:
    root = os.environ.get("ROOT") or os.path.expanduser("~/0luka")
    root = os.path.expandvars(os.path.expanduser(root)).rstrip("/")
    if not root:
        root = os.path.expanduser("~/0luka")
    os.environ["ROOT"] = root
    return root

def _to_ref(path: Path) -> str:
    root = _normalize_root()
    p = str(path)
    if p == root:
        return "${ROOT}"
    prefix = root + os.sep
    if p.startswith(prefix):
        return "${ROOT}" + p[len(root):]
    return p

def _load_policy(policy_path: Path) -> dict:
    return yaml.safe_load(policy_path.read_text())

def _append_beacon(beacon_path: Path, record: dict) -> None:
    beacon_path.parent.mkdir(parents=True, exist_ok=True)
    with beacon_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def handle(task_path: Path, policy_path: Path, beacon_path: Path) -> dict:
    task = yaml.safe_load(task_path.read_text())
    policy = _load_policy(policy_path)

    actor = task.get("actor")
    intent = task.get("intent")
    if not actor or not intent:
        return {"status": "rejected", "error": "missing actor/intent"}

    if actor not in policy.get("actors", {}):
        return {"status": "rejected", "error": f"actor not allowed: {actor}"}

    allowed_intents = set(policy["actors"][actor].get("allow", []))
    if intent not in allowed_intents:
        return {"status": "rejected", "error": f"intent not allowed for actor: {intent}"}

    allowed_roots = policy.get("roots", {}).get("writable", [])
    results = {}

    for g in task.get("verification", {}).get("gates", []):
        if g == "gate.fs.purity":
            ok, meta = gate_fs_purity(task, allowed_roots)
        elif g == "gate.hash.match":
            ok, meta = gate_hash_match(task)
        elif g == "gate.proc.clean":
            ok, meta = gate_proc_clean()
        else:
            ok, meta = False, {"error": f"unknown gate: {g}"}
        results[g] = {"ok": ok, "meta": meta}

    if not all(v["ok"] for v in results.values()):
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "event": "task_rejected",
            "ok": False,
            "actor": actor,
            "intent": intent,
            "task": _to_ref(task_path),
            "results": results,
        }
        _append_beacon(beacon_path, rec)
        return {"status": "rejected", "results": results}

    rec = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": "task_committed",
        "ok": True,
        "actor": actor,
        "intent": intent,
        "task": _to_ref(task_path),
        "outputs": task.get("artifacts", {}).get("outputs", []),
        "results": results,
    }
    _append_beacon(beacon_path, rec)
    return {"status": "committed", "results": results}

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 router.py <task.yaml>", file=sys.stderr)
        sys.exit(2)

    here = Path(__file__).resolve().parent
    root = Path(_normalize_root())
    task_path = Path(sys.argv[1]).resolve()
    policy_path = here / "policy.yaml"
    beacon_path = root / "observability/stl/ledger/global_beacon.jsonl"

    out = handle(task_path, policy_path, beacon_path)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    sys.exit(0 if out.get("status") == "committed" else 3)

if __name__ == "__main__":
    main()
