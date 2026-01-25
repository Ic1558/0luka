import json
import os
import time
import sys
from pathlib import Path
from datetime import datetime, timezone

import sys
from pathlib import Path
# Auto-detect root (3 levels up from ops/governance/drift_monitor.py)
ROOT = Path(__file__).parent.parent.parent.resolve()
sys.path.append(str(ROOT / "ops/governance"))
from rpc_client import RPCClient

OUT = Path.home() / "0luka/observability/telemetry/drift/baseline.jsonl"
rpc = RPCClient()

def check_invariants():
    # Only need to check root FS as a critical invariant for drift
    # In a real system, we'd check more gates.
    res = rpc.call("verify_gate", gate_id="gate.fs.root")
    # RPC response structure: [bool, {details}]
    if isinstance(res, list) and not res[0]:
        return (False, res[1])
    return (True, {})

def collect():
    data = {
        "ts_iso": datetime.now().astimezone().isoformat(),
        "load_1m": os.getloadavg()[0]
    }
    
    # Active Enforcement: Check for drift
    ok, details = check_invariants()
    if not ok:
        print(f"⚠️ DRIFT DETECTED: {details}. Triggering FREEZE.")
        rpc.call("set_alarm", active=True)
        data["alarm"] = "ACTIVE"
        data["violations"] = details
    else:
        # Clear alarm if clean (Optional policy choice)
        # rpc.call("set_alarm", active=False)
        data["alarm"] = "CLEAN"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "a") as f:
        f.write(json.dumps(data) + "\n")

if __name__ == "__main__":
    print(f"Starting drift monitor... logging to {OUT}")
    while True:
        try:
            collect()
        except Exception as e:
            print(f"Error in drift collection: {e}")
        time.sleep(30)
