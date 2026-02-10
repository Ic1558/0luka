import yaml
import os
import json
import time
from datetime import datetime
from datetime import datetime
from core.verify.gates_registry import GATES
from core.enforcement import RuntimeEnforcer, PermissionDenied

# KERNEL v1.x - FROZEN
# Phase 1 complete. Feature changes prohibited.

POLICY_PATH = "core/policy.yaml"

def load_policy():
    with open(POLICY_PATH, 'r') as f:
        return yaml.safe_load(f)

def path_under_roots(path, roots):
    path = os.path.abspath(os.path.expanduser(path))
    for root in roots:
        root = os.path.abspath(os.path.expanduser(root))
        if path.startswith(root):
            return True
    return False

def capabilities_subset(requested, allowed):
    for category, caps in requested.items():
        if category not in allowed: return False
        for cap, val in caps.items():
            if val and not allowed[category].get(cap, False):
                return False
    return True

class Router:
    def __init__(self):
        self.policy = load_policy()

    def propose(self, task_spec):
        # 1. Basic Validation
        assert task_spec["version"] == self.policy["defaults"]["required_task_version"]
        assert task_spec["status"] == "proposed"

        # 2. Policy Check
        actor_id = task_spec["actor"]["proposer"]
        pol = self.policy["actors"].get(actor_id)
        if not pol or not pol["can_propose"]:
            return {"status": "rejected", "reason": "actor_prohibit_propose"}

        # 3. Capability Check
        if not capabilities_subset(task_spec["capabilities"], pol["capabilities"]):
            return {"status": "rejected", "reason": "caps_exceeded"}

        # 3.5. Runtime Enforcement (Tool Gate)
        # Check if the proposed operations violate the runtime policy for the proposer's role
        # Mapping: actor_id -> role (simplified)
        role = pol.get("role", "worker") # Default to worker if not specified
        ops = task_spec.get("operations", [])
        for op in ops:
            try:
                RuntimeEnforcer.enforce_tool_access(
                    role=role,
                    tool_name=op["tool"],
                    args=op.get("params", {}),
                    scope=task_spec.get("scope", {})
                )
            except PermissionDenied as e:
                return {"status": "rejected", "reason": f"policy_violation: {str(e)}"}

        # 4. Root Check
        allowed_roots = task_spec["scope"]["allowed_roots"]
        for root in allowed_roots:
            if not path_under_roots(root, pol["allowed_roots"]):
                return {"status": "rejected", "reason": f"root_prohibit: {root}"}
            # Check deny roots
            for deny in pol.get("deny_roots", []):
                if path_under_roots(root, [deny]):
                    return {"status": "rejected", "reason": f"root_denied: {root}"}

        # 5. Persist as Active
        task_id = task_spec["id"]
        task_spec["status"] = "active"
        path = f"artifacts/tasks/open/{task_id}.yaml"
        with open(path, 'w') as f:
            yaml.dump(task_spec, f)
        
        print(f"DEBUG: Task {task_id} ACTIVATED")
        return {"status": "active", "task_id": task_id}

    def audit(self, task_spec, result_bundle):
        # 1. Run Gates
        gate_names = self.policy["verification"]["required_gates_for_commit"]
        # Add task-specific gates
        gate_names = list(set(gate_names + task_spec["verification"].get("gates", [])))
        
        gate_results = {}
        all_pass = True
        for name in gate_names:
            if name in GATES:
                res = GATES[name](task_spec, result_bundle)
                gate_results[name] = res
                if not res["pass"]: all_pass = False
            else:
                gate_results[name] = {"pass": False, "reason": "gate_not_found"}
                all_pass = False

        # 2. Results
        task_id = task_spec["id"]
        if all_pass:
            task_spec["status"] = "committed"
            # Move to closed
            os.rename(f"artifacts/tasks/open/{task_id}.yaml", f"artifacts/tasks/closed/{task_id}.yaml")
            return {"status": "committed", "gates": gate_results}
        else:
            task_spec["status"] = "audit_failed"
            # Move to rejected
            os.rename(f"artifacts/tasks/open/{task_id}.yaml", f"artifacts/tasks/rejected/{task_id}.yaml")
            return {"status": "rejected", "gates": gate_results}
