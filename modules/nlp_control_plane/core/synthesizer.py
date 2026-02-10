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
from typing import Any, Dict, List, Optional
from pathlib import Path
from core.config import ROOT
from core.submit import submit_task
from core.task_dispatcher import dispatch_one

# Integration with Phase 2 / 2.1
from core.tool_selection_policy import sense_target, classify_risk, select_tool, enforce_before_execute, load_policy_memory
from core.run_provenance import append_event

class NLPControlPlaneError(Exception):
    """Base exception for NLP Control Plane violations."""
    def __init__(self, code: str, message: str):
        self.code = str(code)
        self.message = str(message)
        super().__init__(f"[{self.code}] {self.message}")

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
    if "git status" in text:
        risk_hint = "local"
        ops = [{"type": "run", "command": "git status"}]
        intent = "Check git status in the repo"
        evidence_refs = ["command:git"]
        # Use absolute path to ensure policy.sense sees it as local
        target = str(ROOT)
    elif "cloudflare" in text or "protected" in text:
        risk_hint = "protected"
        target = "https://dash.cloudflare.com"
        ops = [{"type": "run", "command": f"firecrawl_scrape {target}"}]
        intent = "Access dash.cloudflare.com for audit"
        evidence_refs = ["file:artifacts/cf_audit.md"]
    else:
        risk_hint = "none"
        target = "echo"
        ops = [{"type": "run", "command": f"echo {nl_command}"}]
        intent = f"Execute: {nl_command}"
        evidence_refs = []

    # ═══════════════════════════════════════════
    # Phase 9: Return only canonical fields
    # ═══════════════════════════════════════════
    return {
        "schema_version": "clec.v1",
        "task_id": task_id,
        "author": author,
        "intent": intent,
        "risk_hint": risk_hint,
        "ops": ops,
        "evidence_refs": evidence_refs
    }

def process_nlp_request(
    nl_command: str, 
    author: str = "gmx", 
    credentials_present: bool = False,
    session_id: str = "default",
    auto_dispatch: bool = True
) -> Dict[str, Any]:
    """
    Main Orchestration pipeline:
    1. Synthesize
    2. Sense & Select Tool (Phase 2.1)
    3. Enforce Policy
    4. Execute (or block)
    """
    # 1. Synthesis (Internal call gets the target)
    task_full = synthesize_to_canonical_task(nl_command, author)
    target_from_synth = str(ROOT) if task_full["risk_hint"] == "local" else (
        "https://dash.cloudflare.com" if task_full["risk_hint"] == "protected" else "echo"
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
    if task["risk_hint"] == "protected":
        risk = "Protected"
    elif task["risk_hint"] == "local":
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
