#!/usr/bin/env python3
"""
Phase 9: NLP Synthesizer & Orchestrator.
Transforms Natural Language into Canonical Task YAML (clec.v1)
and enforces Governance (P2.1) + Provenance (P2).
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pathlib import Path
from core.config import ROOT
from core.submit import submit_task
from core.task_dispatcher import dispatch_one

# Integration with Phase 2 / 2.1
from core.tool_selection_policy import sense_target, classify_risk, select_tool, enforce_before_execute, load_policy_memory
from core.run_provenance import append_event
from modules.linguist.core.analyzer import analyze_intent
from modules.sentry.core.guard import SentryBlockedError, evaluate_request

class NLPControlPlaneError(Exception):
    """Base exception for NLP Control Plane violations."""
    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"[{self.code}] {self.message}")


ALLOWED_OP_TYPES = {"mkdir", "write_text", "copy", "patch_apply", "run"}
RISK_HINT_MAP = {
    "none": "R0",
    "local": "R1",
    "protected": "R3",
}


def _utc_now_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clec_defaults(env_root: Optional[str] = None) -> Dict[str, Any]:
    _ = env_root
    return {
        "ts_utc": _utc_now_z(),
        "call_sign": "nlp_synth_v1",
        "root": "${ROOT}",
    }


def _ensure_runtime_safe_ops(ops: Any) -> List[Dict[str, Any]]:
    if not isinstance(ops, list) or not ops:
        raise NLPControlPlaneError("intent_not_runtime_safe", "Task has no executable ops.")
    normalized: List[Dict[str, Any]] = []
    for idx, op in enumerate(ops, start=1):
        if not isinstance(op, dict):
            raise NLPControlPlaneError("intent_not_runtime_safe", "Invalid op payload.")
        normalized_op = dict(op)
        normalized_op.setdefault("op_id", f"op{idx}")
        op_type = str(normalized_op.get("type", "")).strip()
        if op_type not in ALLOWED_OP_TYPES:
            raise NLPControlPlaneError("intent_not_runtime_safe", f"Unsupported op.type: {op_type or 'missing'}")
        normalized.append(normalized_op)
    return normalized


def _risk_class_from_text(text: str) -> str:
    lowered = text.lower()
    if "git status" in lowered:
        return "local"
    if "cloudflare" in lowered or "protected" in lowered:
        return "protected"
    return "none"

def validate_no_sensitive_paths(data: Any) -> bool:
    """Ensure no hardcoded user paths exist in the 'intent' field of data entries."""
    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict) and "/Users/" in str(entry.get("intent", "")):
                return False
    elif isinstance(data, dict) and "/Users/" in str(data.get("intent", "")):
        return False
    return True

def synthesize_to_canonical_task(nl_command: str, author: str = "gmx", task_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Synthesize NL to Canonical Task YAML (clec.v1).
    This is a simplified rule-based mapping for the proof.
    """
    text = nl_command.lower()
    
    # Anti-Cheat: Forbidden request mapping
    if "api keys" in text or "passwords" in text:
        raise NLPControlPlaneError(
            "forbidden_secret_discovery",
            "Forbidden search pattern: sensitive data discovery blocked.",
        )

    task_id = task_id or f"task_{uuid.uuid4().hex[:8]}"
    
    # Mapping logic (Mock for proof)
    risk_class = _risk_class_from_text(text)

    if risk_class == "local":
        ops = [{"type": "run", "command": "git status"}]
        intent = "Check git status in the repo"
        evidence_refs = ["command:git"]
    elif risk_class == "protected":
        target = "https://dash.cloudflare.com"
        ops = [{"type": "run", "command": f"firecrawl_scrape {target}"}]
        intent = "Access dash.cloudflare.com for audit"
        evidence_refs = ["file:artifacts/cf_audit.md"]
    else:
        ops = [{"type": "run", "command": f"echo {nl_command}"}]
        intent = f"Execute: {nl_command}"
        evidence_refs = []

    task: Dict[str, Any] = {
        "schema_version": "clec.v1",
        "task_id": task_id,
        "author": author,
        "intent": intent,
        "risk_hint": RISK_HINT_MAP[risk_class],
        "ops": _ensure_runtime_safe_ops(ops),
        "evidence_refs": evidence_refs
    }
    for k, v in _clec_defaults(env_root=str(ROOT)).items():
        task.setdefault(k, v)
    return task

def process_nlp_request(
    nl_command: str, 
    author: str = "gmx", 
    credentials_present: bool = False,
    session_id: str = "default",
    auto_dispatch: bool = True
) -> Dict[str, Any]:
    """
    Main Orchestration pipeline:
    0. Phase 10 Linguist + Sentry
    1. Synthesize
    2. Sense & Select Tool (Phase 2.1)
    3. Enforce Policy
    4. Execute (or block)
    """
    # 0. Phase 10 guards
    analysis = analyze_intent(nl_command, actor="Phase10Linguist")
    if analysis.get("ambiguity", {}).get("is_ambiguous"):
        return {
            "status": "blocked",
            "reason": "human clarification required",
            "details": analysis.get("ambiguity", {}),
        }
    try:
        evaluate_request(nl_command, analysis, actor="Phase10Sentry")
    except SentryBlockedError as exc:
        raise NLPControlPlaneError(exc.code, exc.message) from exc

    # 1. Synthesis (Internal call gets the target)
    task_full = synthesize_to_canonical_task(nl_command, author)
    risk_class = _risk_class_from_text(nl_command)
    target_from_synth = str(ROOT) if risk_class == "local" else (
        "https://dash.cloudflare.com" if risk_class == "protected" else "echo"
    )

    # Clean task for return/dispatch
    task = {k: v for k, v in task_full.items() if k != "target"}
    
    # 2. Phase 2.1 Governance Gate
    target_context = {
        "target": target_from_synth,
        "intent": task["intent"],
        "credentials_present": credentials_present,
        "session_id": session_id
    }
    
    memory = load_policy_memory()
    sense = sense_target(target_context)
    risk = classify_risk(sense, memory)
    
    # Override risk if synthesizer was certain
    if risk_class == "protected":
        risk = "Protected"
    elif risk_class == "local":
        risk = "Internal-Local"

    decision = select_tool(target_context, sense, risk, memory)
    
    # 3. Enforcement
    # If Protected, this will return allowed=False and emit human.escalate
    enforcement = enforce_before_execute(decision)
    
    if not enforcement.get("allowed"):
        return {
            "status": "blocked",
            "task_id": task["task_id"],
            "reason": enforcement.get("message"),
            "decision": decision
        }

    # 4. Submit + Dispatcher bridge (no direct execution)
    receipt = submit_task(task, task_id=task["task_id"])
    result: Dict[str, Any] = {"status": "submitted", "task_id": task["task_id"], "task": task, "receipt": receipt}
    if auto_dispatch:
        inbox_path = ROOT / str(receipt["inbox_path"])
        dispatch_result = dispatch_one(inbox_path)
        result["dispatch"] = dispatch_result
        result["status"] = str(dispatch_result.get("status", "error"))
    return result
