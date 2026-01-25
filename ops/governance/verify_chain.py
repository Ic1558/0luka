import os
import json
import hashlib
from pathlib import Path

class LedgerAuditor:
    def __init__(self, evid_base="/Users/icmini/0luka/observability/stl/evidence"):
        self.evid_base = Path(evid_base)

    def verify_task_chain(self, task_id):
        task_dir = self.evid_base / task_id
        if not task_dir.exists():
            return {"status": "error", "reason": "Task evidence folder not found"}

        attestations = sorted([f for f in task_dir.glob("*.json")])
        if not attestations:
            return {"status": "empty", "task_id": task_id}

        prev_hash = None
        for i, attn_path in enumerate(attestations):
            with open(attn_path, 'r') as f:
                data = json.load(f)
            
            # 1. Check prev_attn_hash link
            if i == 0:
                if data.get("prev_attn_hash") is not None:
                    return {"status": "fail", "reason": "Root attestation has prev_hash", "file": attn_path.name}
            else:
                if data.get("prev_attn_hash") != prev_hash:
                    return {"status": "fail", "reason": "Broken hash chain", "file": attn_path.name}

            # 2. Verify this_attn_hash integrity
            # Extract content minus the this_attn_hash field for verification
            verify_data = {k: v for k, v in data.items() if k != "this_attn_hash"}
            json_str = json.dumps(verify_data, sort_keys=True)
            current_hash = hashlib.sha256(json_str.encode()).hexdigest()
            
            if data.get("this_attn_hash") != current_hash:
                return {"status": "fail", "reason": "Content tampered / Hash mismatch", "file": attn_path.name}
            
            prev_hash = current_hash

        return {"status": "pass", "task_id": task_id, "chain_length": len(attestations)}

if __name__ == "__main__":
    import sys
    auditor = LedgerAuditor()
    if len(sys.argv) > 1:
        print(json.dumps(auditor.verify_task_chain(sys.argv[1]), indent=2))
    else:
        # Verify all tasks
        results = {}
        for d in Path(auditor.evid_base).iterdir():
            if d.is_dir():
                results[d.name] = auditor.verify_task_chain(d.name)
        print(json.dumps(results, indent=2))
