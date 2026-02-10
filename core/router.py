import yaml
import os
import json
import time
from pathlib import Path
from datetime import datetime
from datetime import datetime
from core.verify.gates_registry import GATES
from core.enforcement import RuntimeEnforcer, PermissionDenied
from core.phase1d_result_gate import ResultGateError, gate_outbound_result
from core.outbox_writer import OutboxWriterError, write_result_to_outbox
try:
    from jsonschema import ValidationError, validate as jsonschema_validate
except ImportError:
    ValidationError = Exception  # type: ignore[assignment]
    jsonschema_validate = None

POLICY_PATH = "core/policy.yaml"
REPO_ROOT = Path(__file__).resolve().parents[1]
ROUTER_AUDIT_SCHEMA_PATH = REPO_ROOT / "interface" / "schemas" / "router_audit_v1.json"
_ROUTER_AUDIT_SCHEMA_CACHE = None

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


def _load_router_audit_schema():
    global _ROUTER_AUDIT_SCHEMA_CACHE
    if jsonschema_validate is None:
        raise RuntimeError("missing dependency: jsonschema (pip install jsonschema)")
    if _ROUTER_AUDIT_SCHEMA_CACHE is None:
        if not ROUTER_AUDIT_SCHEMA_PATH.exists():
            raise RuntimeError(f"audit_schema_not_found:{ROUTER_AUDIT_SCHEMA_PATH}")
        try:
            _ROUTER_AUDIT_SCHEMA_CACHE = json.loads(
                ROUTER_AUDIT_SCHEMA_PATH.read_text(encoding="utf-8")
            )
        except Exception as exc:
            raise RuntimeError(f"audit_schema_invalid_json:{exc}") from exc
        if not isinstance(_ROUTER_AUDIT_SCHEMA_CACHE, dict):
            raise RuntimeError("audit_schema_invalid_root")
    return _ROUTER_AUDIT_SCHEMA_CACHE


def _validate_router_audit(payload: dict) -> None:
    schema = _load_router_audit_schema()
    try:
        jsonschema_validate(instance=payload, schema=schema)
    except ValidationError as exc:
        raise RuntimeError(f"audit_schema_invalid:{exc.message}") from exc


def _safe_rename(src: str, dst: str) -> bool:
    """Move src -> dst safely.

    - Returns False if src does not exist or is not a file.
    - Ensures destination parent directories exist.
    - Uses os.replace for an atomic move on the same filesystem.
    """
    try:
        if not src or not dst:
            return False
        if not os.path.exists(src):
            return False
        if not os.path.isfile(src):
            return False
        parent = os.path.dirname(dst)
        if parent:
            os.makedirs(parent, exist_ok=True)
        os.replace(src, dst)
        return True
    except Exception:
        return False


def _write_audit(
    task_id: str,
    decision: str,
    reason: str = "",
    trace_id: str = "",
    intent: str = "",
    executor: str = "",
    resolved_refs: list = None,
    evidence_paths: list = None,
    gate_results: dict = None,
) -> str:
    """Write audit artifact atomically. Returns path or raises on failure."""
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    audit = {
        "schema_version": "router_audit_v1",
        "task_id": task_id,
        "trace_id": trace_id or task_id,
        "ts_utc": ts,
        "intent": intent,
        "executor": executor,
        "decision": decision,
        "reason": reason,
        "resolved_refs": resolved_refs or [],
        "evidence_paths": evidence_paths or [],
        "gate_results": gate_results or {},
    }

    audit_str = json.dumps(audit, ensure_ascii=False)
    if "/Users/" in audit_str or "file:///Users" in audit_str:
        raise RuntimeError("audit_contains_hard_paths")

    # Schema validation (fail-closed)
    _validate_router_audit(audit)

    root_env = os.environ.get("ROOT", "").strip()
    root = Path(root_env).expanduser().resolve(strict=False) if root_env else Path(__file__).resolve().parents[1]
    out_dir = root / "observability" / "artifacts" / "router_audit"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{task_id}.json"
    tmp_path = out_dir / f".{task_id}.tmp"

    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(audit, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp_path, out_path)
    return str(out_path)

class Router:
    def __init__(self):
        self.policy = load_policy()

    def execute(self, task_spec):
        schema_version = task_spec.get("schema_version")
        if schema_version == "clec.v1":
            from core.clec_executor import CLECExecutorError, execute_clec_ops

            ops = task_spec.get("ops", [])
            verify = task_spec.get("verify", [])
            try:
                status, evidence = execute_clec_ops(ops, {}, verify)
            except CLECExecutorError as exc:
                return {"status": "error", "reason": str(exc), "evidence": {}}
            return {"status": status, "evidence": evidence}
        return {"status": "unsupported_schema", "reason": "schema_not_routable"}

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
        task_id = task_spec.get("id", "unknown")
        intent = task_spec.get("intent", "")
        executor = task_spec.get("actor", {}).get("proposer", "")
        trace_id = result_bundle.get("trace_id", task_id)

        resolved_refs = []
        resolved = (result_bundle.get("resolved") or {}).get("resources") or []
        for res in resolved:
            ref = res.get("ref", "")
            if ref.startswith("ref://"):
                resolved_refs.append(ref)

        evidence_paths = []
        evidence = result_bundle.get("evidence") or {}
        for key in ["logs", "commands", "effects"]:
            items = evidence.get(key) or []
            if items:
                evidence_paths.append(f"evidence.{key}[{len(items)}]")

        gate_names = self.policy["verification"]["required_gates_for_commit"]
        gate_names = list(set(gate_names + task_spec["verification"].get("gates", [])))

        gate_results = {}
        all_pass = True
        for name in gate_names:
            if name in GATES:
                res = GATES[name](task_spec, result_bundle)
                gate_results[name] = res
                if not res["pass"]:
                    all_pass = False
            else:
                gate_results[name] = {"pass": False, "reason": "gate_not_found"}
                all_pass = False

        if not all_pass:
            try:
                _write_audit(
                    task_id=task_id,
                    decision="rejected",
                    reason="gates_failed",
                    trace_id=trace_id,
                    intent=intent,
                    executor=executor,
                    resolved_refs=resolved_refs,
                    evidence_paths=evidence_paths,
                    gate_results=gate_results,
                )
            except Exception:
                pass

            task_spec["status"] = "audit_failed"
            _safe_rename(
                f"artifacts/tasks/open/{task_id}.yaml",
                f"artifacts/tasks/rejected/{task_id}.yaml"
            )
            return {"status": "rejected", "gates": gate_results}

        # Happy path ordering: gate checks -> audit write -> outbound write.
        try:
            _write_audit(
                task_id=task_id,
                decision="ok",
                trace_id=trace_id,
                intent=intent,
                executor=executor,
                resolved_refs=resolved_refs,
                evidence_paths=evidence_paths,
                gate_results=gate_results,
            )
        except Exception as exc:
            task_spec["status"] = "audit_failed"
            _safe_rename(
                f"artifacts/tasks/open/{task_id}.yaml",
                f"artifacts/tasks/rejected/{task_id}.yaml"
            )
            return {"status": "rejected", "reason": f"audit_write_failed:{exc}"}

        try:
            result_bundle = gate_outbound_result(result_bundle)
            write_result_to_outbox(result_bundle)
        except ResultGateError as exc:
            try:
                _write_audit(
                    task_id=task_id,
                    decision="error",
                    reason=f"outbound_result_gate_failed:{exc}",
                    trace_id=trace_id,
                    intent=intent,
                    executor=executor,
                    resolved_refs=resolved_refs,
                    evidence_paths=evidence_paths,
                )
            except Exception:
                pass

            task_spec["status"] = "audit_failed"
            _safe_rename(
                f"artifacts/tasks/open/{task_id}.yaml",
                f"artifacts/tasks/rejected/{task_id}.yaml"
            )
            return {"status": "rejected", "reason": f"outbound_result_gate_failed:{exc}"}

        except OutboxWriterError as exc:
            try:
                _write_audit(
                    task_id=task_id,
                    decision="error",
                    reason=f"outbox_write_failed:{exc}",
                    trace_id=trace_id,
                    intent=intent,
                    executor=executor,
                    resolved_refs=resolved_refs,
                    evidence_paths=evidence_paths,
                )
            except Exception:
                pass

            task_spec["status"] = "audit_failed"
            _safe_rename(
                f"artifacts/tasks/open/{task_id}.yaml",
                f"artifacts/tasks/rejected/{task_id}.yaml"
            )
            return {"status": "rejected", "reason": f"outbox_write_failed:{exc}"}

        task_spec["status"] = "committed"
        _safe_rename(
            f"artifacts/tasks/open/{task_id}.yaml",
            f"artifacts/tasks/closed/{task_id}.yaml"
        )
        return {"status": "committed", "gates": gate_results}
