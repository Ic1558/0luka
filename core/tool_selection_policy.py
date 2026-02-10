#!/usr/bin/env python3
"""Phase 2: Tool-selection policy and enforcement layer."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from core.config import ROOT

POLICY_MEMORY_PATH = ROOT / "core" / "state" / "policy_memory.json"
EVENTS_PATH = ROOT / "observability" / "events.jsonl"

BLOCK_KEYWORDS = {
    "cf-challenge",
    "captcha",
    "ddos-guard",
    "datadome",
    "px-captcha",
    "turnstile",
    "blocked-access",
    "403-forbidden",
}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _default_memory() -> Dict[str, Any]:
    return {
        "schema_version": "policy_memory_v1",
        "protected_domains": [],
        "allowlist": [],
        "outcomes": [],
        "updated_at": _utc_now(),
    }


def append_event(event_dict: Dict[str, Any]) -> None:
    EVENTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(event_dict)
    payload.setdefault("ts", _utc_now())
    with EVENTS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_policy_memory() -> Dict[str, Any]:
    if not POLICY_MEMORY_PATH.exists():
        memory = _default_memory()
        write_policy_memory_atomic(memory)
        return memory
    try:
        data = json.loads(POLICY_MEMORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        data = _default_memory()
    if not isinstance(data, dict):
        data = _default_memory()
    data.setdefault("schema_version", "policy_memory_v1")
    data.setdefault("protected_domains", [])
    data.setdefault("allowlist", [])
    data.setdefault("outcomes", [])
    data.setdefault("updated_at", _utc_now())
    return data


def write_policy_memory_atomic(memory: Dict[str, Any]) -> None:
    POLICY_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(memory)
    payload["updated_at"] = _utc_now()
    tmp = POLICY_MEMORY_PATH.parent / ".policy_memory.tmp"
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(POLICY_MEMORY_PATH)


def _extract_domain(target_context: Dict[str, Any]) -> str:
    url = str(target_context.get("url") or target_context.get("target") or "").strip()
    if url.startswith("http://") or url.startswith("https://"):
        return (urlparse(url).hostname or "").lower()
    domain = str(target_context.get("domain") or "").strip().lower()
    return domain


def sense_target(target_context: Dict[str, Any]) -> Dict[str, Any]:
    append_event(
        {
            "type": "policy.sense.started",
            "category": "policy",
            "target": str(target_context.get("target") or target_context.get("url") or ""),
        }
    )
    memory = load_policy_memory()
    text_bits = [
        str(target_context.get("target") or ""),
        str(target_context.get("url") or ""),
        str(target_context.get("task_text") or ""),
        " ".join(str(s) for s in (target_context.get("signals") or [])),
    ]
    haystack = " ".join(text_bits).lower()
    signals: List[str] = []
    confidence = 0.2
    domain = _extract_domain(target_context)
    if domain:
        for row in memory.get("protected_domains", []):
            if isinstance(row, dict) and str(row.get("domain", "")).lower() == domain:
                signals.append("protected_domain_match")
                confidence = max(confidence, 0.95)
                break
    for kw in sorted(BLOCK_KEYWORDS):
        if kw in haystack:
            signals.append(f"keyword:{kw}")
            confidence = max(confidence, 0.9)
    status = int(target_context.get("status_code") or 0)
    headers = {str(k).lower(): str(v).lower() for k, v in (target_context.get("headers") or {}).items()}
    if status == 403 and "cloudflare" in headers.get("server", ""):
        signals.append("http_403_cloudflare")
        confidence = 1.0
    if status == 429:
        signals.append("http_429_rate_limit")
        confidence = max(confidence, 0.8)
    if any(x in haystack for x in ("/login", "/signin", "/auth")):
        signals.append("login_wall")
        confidence = max(confidence, 0.85)
    if any(x in haystack for x in ("puzzle", "drag", "slider")):
        signals.append("human_entropy_required")
        confidence = max(confidence, 0.95)
    if str(target_context.get("target") or "").startswith("/") or str(target_context.get("target") or "").startswith("ref://"):
        signals.append("local_path")
        confidence = max(confidence, 0.9)
    if target_context.get("api_available") is True:
        signals.append("api_available")
        confidence = max(confidence, 0.75)
    return {"signals": signals, "confidence": round(confidence, 2), "domain": domain, "status_code": status, "headers": headers}


def classify_risk(sense_result: Dict[str, Any], policy_memory: Dict[str, Any]) -> str:
    del policy_memory
    signals = set(str(s) for s in sense_result.get("signals", []))
    if "local_path" in signals:
        return "Internal-Local"
    if "api_available" in signals:
        return "API-First"
    if {"http_403_cloudflare", "protected_domain_match"} & signals:
        return "Protected"
    if any(sig.startswith("keyword:") for sig in signals) or "human_entropy_required" in signals:
        return "Protected"
    if "login_wall" in signals:
        return "Authenticated"
    return "Public-Unprotected"


def _required_evidence_for(risk_class: str, target_context: Dict[str, Any]) -> List[Dict[str, str]]:
    target = str(target_context.get("target") or target_context.get("url") or "")
    if risk_class == "Protected":
        return [{"kind": "screenshot", "ref": target}, {"kind": "user_confirmation", "ref": "manual_step_ack"}]
    if risk_class == "Authenticated":
        return [{"kind": "screenshot", "ref": target}, {"kind": "user_confirmation", "ref": "authenticated_manual_ack"}]
    if risk_class == "Public-Unprotected":
        return [{"kind": "report", "ref": "content_md5 + cite_url"}]
    if risk_class == "Internal-Local":
        return [{"kind": "file", "ref": target}, {"kind": "log", "ref": "line_count"}]
    if risk_class == "API-First":
        return [{"kind": "command", "ref": "api_status_200"}]
    return [{"kind": "report", "ref": "blocked"}]


def _tool_for_risk(risk_class: str, target_context: Dict[str, Any]) -> str:
    if risk_class == "Protected":
        return "HUMAN_BROWSER"
    if risk_class == "Authenticated":
        return "OFFICIAL_API" if target_context.get("api_available") else "HUMAN_BROWSER"
    if risk_class == "Public-Unprotected":
        return "FIRECRAWL_SCRAPE"
    if risk_class == "Internal-Local":
        target = str(target_context.get("target") or "")
        return "READ_FILE" if target else "CLI"
    if risk_class == "API-First":
        return "OFFICIAL_API"
    return "BLOCKED"


def select_tool(
    target_context: Dict[str, Any],
    sense_result: Dict[str, Any],
    risk_class: str,
    policy_memory: Dict[str, Any],
) -> Dict[str, Any]:
    del policy_memory
    tool = _tool_for_risk(risk_class, target_context)
    domain = sense_result.get("domain", "")
    rationale = f"risk={risk_class}; signals={','.join(sense_result.get('signals', [])) or 'none'}"
    human_required = bool(risk_class in {"Protected", "Authenticated"} and tool == "HUMAN_BROWSER")
    if risk_class == "Protected":
        rationale = f"Protected domain detected ({domain or 'unknown'}), headless automation blocked."
    decision = {
        "tool": tool,
        "risk_class": risk_class,
        "human_required": human_required,
        "rationale": rationale,
        "required_evidence": _required_evidence_for(risk_class, target_context),
        "next_steps": ["run_policy_enforcement"],
        "sense": {"signals": list(sense_result.get("signals", [])), "confidence": float(sense_result.get("confidence", 0.0))},
        "policy_updates": [],
    }
    append_event(
        {
            "type": "policy.decide.completed",
            "category": "policy",
            "tool": decision["tool"],
            "risk_class": decision["risk_class"],
            "human_required": decision["human_required"],
        }
    )
    return decision


def _human_required_message(domain: str, action_name: str) -> str:
    return (
        f"Policy Restriction: The domain {domain} is classified as Protected. "
        f"Headless automation is blocked to prevent detection/lockout. "
        f"Please {action_name} manually and let me know when complete."
    )


def enforce_before_execute(decision: Dict[str, Any], execution_tool: Optional[str] = None) -> Dict[str, Any]:
    risk = str(decision.get("risk_class", ""))
    selected = str(decision.get("tool", "BLOCKED"))
    requested = (execution_tool or selected).upper()
    blocked_matrix = {
        "Protected": {"FIRECRAWL_SCRAPE", "BROWSER_SUBAGENT", "HEADLESS_AUTOMATION"},
        "Authenticated": {"FIRECRAWL_SCRAPE", "BROWSER_SUBAGENT", "HEADLESS_AUTOMATION"},
        "API-First": {"FIRECRAWL_SCRAPE"},
    }
    if selected == "BLOCKED" or requested in blocked_matrix.get(risk, set()):
        domain = str(decision.get("sense", {}).get("domain") or "unknown-domain")
        action_name = str(decision.get("next_steps", ["[Enter Action Name]"])[0] or "[Enter Action Name]")
        message = _human_required_message(domain, action_name) if risk == "Protected" else f"Blocked by policy matrix ({risk}): {requested}"
        append_event(
            {
                "type": "policy.enforce.blocked",
                "category": "policy",
                "risk_class": risk,
                "selected_tool": selected,
                "requested_tool": requested,
            }
        )
        if risk == "Protected":
            append_event(
                {
                    "type": "policy.human_escalation.requested",
                    "category": "policy",
                    "risk_class": risk,
                    "domain": domain,
                    "message": message,
                }
            )
        return {"allowed": False, "message": message}
    if bool(decision.get("human_required")):
        domain = str(decision.get("sense", {}).get("domain") or "unknown-domain")
        action_name = str(decision.get("next_steps", ["[Enter Action Name]"])[0] or "[Enter Action Name]")
        message = _human_required_message(domain, action_name)
        append_event(
            {
                "type": "policy.enforce.blocked",
                "category": "policy",
                "risk_class": risk,
                "selected_tool": selected,
                "requested_tool": requested,
            }
        )
        append_event(
            {
                "type": "policy.human_escalation.requested",
                "category": "policy",
                "risk_class": risk,
                "domain": domain,
                "message": message,
            }
        )
        return {"allowed": False, "message": message}
    return {"allowed": True}


def _upsert_protected_domain(memory: Dict[str, Any], domain: str) -> None:
    rows = memory.setdefault("protected_domains", [])
    now = _utc_now()
    for row in rows:
        if isinstance(row, dict) and str(row.get("domain", "")).lower() == domain.lower():
            row["hits"] = int(row.get("hits", 0)) + 1
            row["last_blocked"] = now
            return
    rows.append({"domain": domain.lower(), "hits": 1, "last_blocked": now})


def reflect_update_policy(decision: Dict[str, Any], outcome: Dict[str, Any], policy_memory: Dict[str, Any]) -> Dict[str, Any]:
    updated = json.loads(json.dumps(policy_memory))
    domain = str(outcome.get("domain") or decision.get("sense", {}).get("domain") or "").strip().lower()
    status = int(outcome.get("status", 0))
    headers = {str(k).lower(): str(v).lower() for k, v in (outcome.get("headers") or {}).items()}
    updates: List[Dict[str, Any]] = []
    if domain and status == 403 and "cloudflare" in headers.get("server", ""):
        _upsert_protected_domain(updated, domain)
        updates.append({"op": "add_protected_domain", "domain": domain, "hits_inc": 1})
    updated.setdefault("outcomes", []).append(
        {
            "ts": _utc_now(),
            "domain": domain,
            "status": status,
            "tool": decision.get("tool"),
            "risk_class": decision.get("risk_class"),
        }
    )
    write_policy_memory_atomic(updated)
    decision_updates = decision.setdefault("policy_updates", [])
    decision_updates.extend(updates)
    append_event(
        {
            "type": "policy.reflect.updated",
            "category": "policy",
            "domain": domain,
            "status": status,
            "updates": updates,
        }
    )
    return updated


def emit_policy_verified_if_proven(actor: str = "PolicyEnforcer") -> bool:
    memory = load_policy_memory()
    domains = memory.get("protected_domains", [])
    protected_ok = isinstance(domains, list) and len(domains) >= 3
    escalation_found = False
    if EVENTS_PATH.exists():
        for line in EVENTS_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get("type") == "policy.human_escalation.requested":
                escalation_found = True
                break
    if protected_ok and escalation_found:
        append_event(
            {
                "type": "policy.verified",
                "category": "policy",
                "actor": actor,
                "proof": {
                    "protected_domains_count": len(domains),
                    "has_human_escalation_event": escalation_found,
                    "memory_path": str(POLICY_MEMORY_PATH),
                    "events_path": str(EVENTS_PATH),
                },
            }
        )
        return True
    return False
