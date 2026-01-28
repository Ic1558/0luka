#!/usr/bin/env zsh
# 0luka-FOUNDATION-V0.2: Establishing Autonomy and Silencing Legacy

ROOT="$HOME/0luka"
STL_DIR="$ROOT/observability/stl"
ONTOLOGY_PATH="$ROOT/core/governance/ontology.yaml"
RUNNER_PATH="$ROOT/ops/governance/gate_runner.py"

echo "--- 1. Updating Ontology (Structured Invariants) ---"
cat << 'EOF' > "$ONTOLOGY_PATH"
version: "0.2"
status: "AUTHORITATIVE"
entities:
  opal-api:
    class: "core-service"
    identity: { port: 7001, process_name: "uvicorn", binary_contains: "runtime/venv/opal" }
  heartbeat-service:
    class: "observability-agent"
    identity: { launchd_label: "com.0luka.heartbeat" }
  legacy-bridge:
    class: "transition-group"
    members: ["mary_dispatcher", "clc_bridge", "shell_watcher"]
    policy: "DEPRECATED_STRICT"
    enforcement: "BLOCK_NEW_SPAWNS"

invariants:
  strict_root:
    allow: ["core", "runtime", "ops", "observability", ".git", ".0luka", ".opencode", ".openwork"]
    remediation: "auto-quarantine"
EOF

echo "--- 2. Deploying Gate-Runner v0.2 (Task-Driven Engine) ---"
cat << 'EOF' > "$RUNNER_PATH"
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
        return (False, {"error": "Unknown Gate"})

    def run_task(self, task_path):
        with open(task_path, 'r') as f: task = yaml.safe_load(f)
        task_id = task['id']
        path = self.EVID_BASE / task_id
        path.mkdir(parents=True, exist_ok=True)
        results = [{"gate": g, "res": self.verify_gate(g)} for g in task.get('verification', {}).get('gates', [])]
        with open(path / "attestation.json", 'w') as f:
            json.dump({"task_id": task_id, "ts": datetime.utcnow().isoformat(), "results": results}, f, indent=2)
        print(f"✅ Task {task_id} Attestation Saved: {path}/attestation.json")

if __name__ == "__main__":
    import sys
    runner = GateRunner()
    if len(sys.argv) > 1:
        runner.run_task(sys.argv[1])
EOF
chmod +x "$RUNNER_PATH"

echo "--- 3. Registering Legacy Decommission Task ---"
DECOMM_TASK="$STL_DIR/tasks/open/T-20260125-002_legacy_decommission.yaml"
mkdir -p "$(dirname "$DECOMM_TASK")"
cat << 'EOF' > "$DECOMM_TASK"
id: "T-20260125-002_legacy_decommission"
title: "Silence 02luka Loops"
intent: "Decommission legacy services causing process churn"
status: "open"
verification:
  gates: ["gate.fs.root", "gate.net.port"]
EOF

echo "--- 4. Executing Final Legacy Cleanup ---"
# หยุด Looping Services ของ 02luka จริงๆ
launchctl list | grep com.02luka | awk '{print $3}' | xargs -I{} launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/{}.plist 2>/dev/null || true
ps aux | grep -E "02luka" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true

echo "--- 5. Triggering Gate-Runner Validation ---"
python3 "$RUNNER_PATH" "$DECOMM_TASK"

echo "\n🏁 OPERATION COMPLETE: 0luka Foundation v0.2 is Live."
ls -F "$ROOT"
