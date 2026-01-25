import sys
import os
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from core.router import Router
from core.ledger.ledger import ledger_append
from plugins.executors.shell_exec import ShellExecutor

def test_v1_loop():
    print("--- 0luka v1.0 Architecture Test ---")
    
    router = Router()
    executor = ShellExecutor()
    
    # 1. Prepare TaskSpec v1.0
    task_id = f"260126_023000_task_test_{os.getpid()}"
    task_spec = {
        "id": task_id,
        "version": "1.0",
        "meta": {
            "created_at": datetime.now().astimezone().isoformat(),
            "kind": "task",
            "trace_id": f"t_{task_id}",
            "tags": ["test"]
        },
        "actor": {
            "proposer": "agent.osaurus",
            "executor_hint": "module.execution.shell",
            "approval": "auto"
        },
        "capabilities": {
            "filesystem": {"read": True, "write": True, "delete": True},
            "process": {"spawn": True},
            "network": {"outbound": False}
        },
        "scope": {
            "workspace_root": "~/0luka",
            "allowed_roots": ["~/0luka/artifacts"]
        },
        "intent": {
            "summary": "Core v1.0 loop test",
            "success_criteria": ["artifact created"]
        },
        "artifacts": {
            "outputs": [{"path": "~/0luka/artifacts/v1_test_output.txt", "required": True}]
        },
        "verification": {
            "gates": ["gate.fs.purity", "gate.hash.match"]
        },
        "status": "proposed"
    }

    # 2. Propose
    print("\n[STEP 1: PROPOSE]")
    res = router.propose(task_spec)
    if res["status"] != "active":
        print(f"FAILED: {res}")
        return

    # 3. Execute
    print("\n[STEP 2: EXECUTE]")
    result_bundle = executor.execute(task_spec)
    print(f"Executor Result: {result_bundle['outcome']['summary']}")

    # 4. Audit & Commit
    print("\n[STEP 3: AUDIT & COMMIT]")
    audit_res = router.audit(task_spec, result_bundle)
    
    print(f"Audit Status: {audit_res['status']}")
    for gate, gres in audit_res.get("gates", {}).items():
        status = "✅" if gres["pass"] else "❌"
        print(f"  {status} {gate}: {gres.get('reason')}")

    if audit_res["status"] == "committed":
        print("\n🏆 TEST SUCCESS: Core v1.0 transition verified.")
        # Commit success to ledger
        ledger_append("TEST_SUCCESS", {"task_id": task_id, "architecture": "v1.0"})
    else:
        print("\n❌ TEST FAILED.")

if __name__ == "__main__":
    test_v1_loop()
