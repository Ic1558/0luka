import json, yaml, socket, os
from pathlib import Path
from datetime import datetime

class GateRunner:
    def __init__(self):
        self.ROOT = Path.home() / "0luka"
        self.EVID_BASE = self.ROOT / "observability/stl/evidence"
        with open(self.ROOT / "core/governance/ontology.yaml", 'r') as f:
            self.ontology = yaml.safe_load(f)

    def verify_gate(self, gate_id):
        if gate_id == "gate.fs.root":
            allowed = set(self.ontology['invariants']['strict_root']['allow'])
            current = set([f.name for f in self.ROOT.iterdir() if not f.name.startswith('.')])
            violations = current - allowed
            return (not violations, {"violations": list(violations)})
        if gate_id == "gate.net.port":
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                ok = s.connect_ex(('localhost', 7001)) == 0
            return (ok, {"port": 7001})
        if gate_id == "gate.perf.memory":
            import subprocess
            res = subprocess.check_output("ps aux | grep -E 'uvicorn|heartbeat' | grep -v grep | awk '{print $4, $11}'", shell=True).decode()
            return (True, {"memory_usage_pct": res.strip().split('\n')})
        if gate_id == "gate.proc.purity":
            import subprocess
            res = subprocess.check_output("ps aux | grep -Ei 'mary_dispatcher|clc_bridge|shell_watcher' | grep -v grep | wc -l", shell=True).decode()
            count = int(res.strip())
            return (count == 0, {"legacy_proc_count": count})
        return (False, {"error": f"Unknown Gate: {gate_id}"})

    def run_gates(self, gates):
        return {g: self.verify_gate(g) for g in gates}

    def execute_action(self, action_id, task_id):
        import subprocess
        action = self.ontology.get('actions', {}).get(action_id)
        if not action:
            return (False, {"error": f"Action {action_id} not in allowlist"})
        
        # 1. Pre-Gates
        pre_results = self.run_gates(action.get('pre_gates', []))
        if not all(res[0] for res in pre_results.values()):
            return (False, {"error": "Pre-gates failed", "results": pre_results})
        
        # 2. Handler Execution
        handler = self.ROOT / action['handler']
        try:
            res = subprocess.check_output(str(handler), shell=True).decode()
        except subprocess.CalledProcessError as e:
            return (False, {"error": "Handler failed", "output": e.output.decode()})
            
        # 3. Post-Gates
        post_results = self.run_gates(action.get('post_gates', []))
        return (all(res[0] for res in post_results.values()), {"results": post_results, "output": res})

    def run_task(self, task_path):
        import hashlib
        task_path = Path(task_path)
        task_id = task_path.name
        
        with open(task_path, 'r') as f: 
            task_content = f.read()
            task = yaml.safe_load(task_content)
        
        path = self.EVID_BASE / task_id
        path.mkdir(parents=True, exist_ok=True)
        
        results = [{"gate": g, "res": self.verify_gate(g)} for g in task.get('verification', {}).get('gates', [])]
        
        # Generate Canonical Attestation ID
        now = datetime.now()
        ts_str = now.strftime("%y%m%d_%H%M%S")
        slug = task_id.split('_')[2] if '_' in task_id else "task"
        
        data = {"task_id": task_id, "ts": now.astimezone().isoformat(), "results": results}
        json_str = json.dumps(data, indent=2)
        h8 = hashlib.sha256(json_str.encode()).hexdigest()[:8]
        
        attn_filename = f"{ts_str}_attn_{slug}_{h8}.json"
        
        with open(path / attn_filename, 'w') as f:
            f.write(json_str)
            
        print(f"✅ Task {task_id} Attestation Saved: {path}/{attn_filename}")

if __name__ == "__main__":
    import sys
    runner = GateRunner()
    if len(sys.argv) > 1:
        runner.run_task(sys.argv[1])
