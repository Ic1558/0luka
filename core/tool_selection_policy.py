#!/usr/bin/env python3
"""Phase 2.1: Tool-selection policy + DJM reasoning + safety guards."""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from core.config import ROOT
from core.reasoning_audit import REASONING_AUDIT_PATH, append_reasoning_entry, load_reasoning_entries

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

HEADLESS_TOOLS = {"FIRECRAWL_SCRAPE", "BROWSER_SUBAGENT", "HEADLESS_AUTOMATION", "READ_URL_CONTENT"}
AUTOMATION_TOOLS = {"OFFICIAL_API", "CLI", "FIRECRAWL_SCRAPE", "READ_URL_CONTENT", "BROWSER_SUBAGENT", "HEADLESS_AUTOMATION"}
PROTECTION_HEADERS = {"cloudflare", "datadome", "perimeterx", "akamai"}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _epoch_now() -> int:
    return int(time.time())


def _default_memory() -> Dict[str, Any]:
    return {
        "schema_version": "policy_memory_v2_1",
        "protected_domains": [],
        "allowlist": [],
        "outcomes": [],
        "authenticated_retry_sessions": {},
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
    data.setdefault("schema_version", "policy_memory_v2_1")
    data.setdefault("protected_domains", [])
    data.setdefault("allowlist", [])
    data.setdefault("outcomes", [])
    data.setdefault("authenticated_retry_sessions", {})
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
    return str(target_context.get("domain") or "").strip().lower()


def _is_local_target(target_context: Dict[str, Any]) -> bool:
    target = str(target_context.get("target") or "")
    return target.startswith("/") or target.startswith("ref://")


def _has_protection_header(headers: Dict[str, str]) -> bool:
    for value in headers.values():
        v = str(value).lower()
        if any(sig in v for sig in PROTECTION_HEADERS):
            return True
    return False


def _protected_record(memory: Dict[str, Any], domain: str) -> Optional[Dict[str, Any]]:
    for row in memory.get("protected_domains", []):
        if isinstance(row, dict) and str(row.get("domain", "")).lower() == domain.lower():
            return row
    return None


def _is_confirmed_protected(memory: Dict[str, Any], domain: str) -> bool:
    row = _protected_record(memory, domain)
    if not row:
        return False
    return str(row.get("state", "")).upper() == "CONFIRMED"


def _append_violation(reason: str, decision: Optional[Dict[str, Any]] = None, requested_tool: str = "") -> None:
    payload = {
        "type": "policy.violation",
        "category": "policy",
        "reason": reason,
        "requested_tool": requested_tool,
    }
    if decision:
        payload["risk_class"] = decision.get("risk_class")
        payload["tool"] = decision.get("tool")
        payload["domain"] = decision.get("sense", {}).get("domain")
    append_event(payload)


def sense_target(target_context: Dict[str, Any]) -> Dict[str, Any]:
    append_event(
        {
            "type": "policy.sense.started",
            "category": "policy",
            "target": str(target_context.get("target") or target_context.get("url") or ""),
            "intent": str(target_context.get("intent") or ""),
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

    if domain and _protected_record(memory, domain):
        signals.append("protected_domain_match")
        confidence = max(confidence, 0.95)

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
    if _is_local_target(target_context):
        signals.append("local_path")
        confidence = max(confidence, 0.9)
    if target_context.get("api_available") is True:
        signals.append("api_available")
        confidence = max(confidence, 0.75)

    confidence = round(confidence, 2)
    return {
        "signals": signals,
        "confidence": confidence,
        "confidence_score": confidence,
        "domain": domain,
        "status_code": status,
        "headers": headers,
    }


def classify_risk(sense_result: Dict[str, Any], policy_memory: Dict[str, Any]) -> str:
    signals = set(str(s) for s in sense_result.get("signals", []))
    domain = str(sense_result.get("domain") or "")
    if "local_path" in signals:
        return "Internal-Local"
    if "api_available" in signals:
        return "API-First"
    if domain and _is_confirmed_protected(policy_memory, domain):
        return "Protected"
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
        return [
            {"kind": "screenshot", "ref": target},
            {"kind": "user_confirmation", "ref": "manual_step_ack"},
        ]
    if risk_class == "Authenticated":
        return [
            {"kind": "screenshot", "ref": target},
            {"kind": "user_confirmation", "ref": "authenticated_manual_ack"},
        ]
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
        if target_context.get("credentials_present") and target_context.get("api_available"):
            return "OFFICIAL_API"
        return "HUMAN_BROWSER"
    if risk_class == "Public-Unprotected":
        return "FIRECRAWL_SCRAPE"
    if risk_class == "Internal-Local":
        target = str(target_context.get("target") or "")
        return "READ_FILE" if target else "CLI"
    if risk_class == "API-First":
        return "OFFICIAL_API"
    return "BLOCKED"


def _build_djm(target_context: Dict[str, Any], sense_result: Dict[str, Any], risk_class: str, tool: str, human_required: bool) -> Dict[str, Any]:
    policy_rule = f"RISK_{risk_class.replace('-', '_').upper()}"
    alternatives = [
        {"tool": "HUMAN_BROWSER", "reason": "Manual mode not required"},
        {"tool": "OFFICIAL_API", "reason": "No API-first requirement"},
        {"tool": "FIRECRAWL_SCRAPE", "reason": "Blocked by risk policy"},
        {"tool": "READ_URL_CONTENT", "reason": "Not selected path"},
    ]
    alternatives = [row for row in alternatives if row["tool"] != tool]
    human_justification = ""
    if human_required:
        domain = str(sense_result.get("domain") or "unknown-domain")
        human_justification = (
            "Manual execution required to avoid anti-bot lockout and preserve account safety "
            f"for domain {domain}."
        )

    return {
        "sense_summary": {
            "signals": list(sense_result.get("signals", [])),
            "confidence_score": float(sense_result.get("confidence_score", sense_result.get("confidence", 0.0))),
        },
        "policy_rule_applied": policy_rule,
        "logic_path": f"sense -> classify({risk_class}) -> select({tool})",
        "alternatives_rejected": alternatives,
        "human_justification": human_justification,
    }


def select_tool(
    target_context: Dict[str, Any],
    sense_result: Dict[str, Any],
    risk_class: str,
    policy_memory: Dict[str, Any],
) -> Dict[str, Any]:
    if not sense_result:
        _append_violation("sense_missing_precondition", requested_tool="")
        raise RuntimeError("sense_missing_precondition")

    tool = _tool_for_risk(risk_class, target_context)
    domain = str(sense_result.get("domain") or "")
    confidence = float(sense_result.get("confidence_score", sense_result.get("confidence", 0.0)))

    mandatory_human = risk_class == "Protected" or (
        risk_class == "Authenticated" and not bool(target_context.get("credentials_present"))
    )
    optional_human = (confidence < 0.5) and (risk_class not in {"Protected", "Authenticated"})
    human_required = mandatory_human or optional_human

    if risk_class == "Protected":
        rationale = f"Protected target {domain or 'unknown'}; automation blocked"
    elif mandatory_human:
        rationale = "Authenticated target missing credentials; manual escalation required"
    elif optional_human:
        rationale = "Low confidence classification; escalate to human"
    else:
        rationale = f"risk={risk_class}; confidence={confidence:.2f}"

    policy_updates: List[Dict[str, Any]] = []
    if domain and _is_confirmed_protected(policy_memory, domain):
        policy_updates.append({"op": "frozen_protected_domain", "domain": domain})

    decision = {
        "tool": tool,
        "risk_class": risk_class,
        "human_required": bool(human_required),
        "rationale": rationale,
        "required_evidence": _required_evidence_for(risk_class, target_context),
        "next_steps": ["Login/Solve Challenge"],
        "sense": {
            "signals": list(sense_result.get("signals", [])),
            "confidence": confidence,
            "domain": domain,
        },
        "policy_updates": policy_updates,
        "session_id": str(target_context.get("session_id") or "default"),
        "target": str(target_context.get("target") or target_context.get("url") or ""),
        "credentials_present": bool(target_context.get("credentials_present")),
    }

    djm = _build_djm(target_context, sense_result, risk_class, tool, human_required)
    decision["djm"] = djm

    try:
        append_event(
            {
                "type": "policy.decide.completed",
                "category": "policy",
                "tool": decision["tool"],
                "risk_class": decision["risk_class"],
                "human_required": decision["human_required"],
            }
        )
        append_event(
            {
                "type": "policy.reasoning.select",
                "category": "policy",
                "risk_class": decision["risk_class"],
                "tool": decision["tool"],
                "human_required": decision["human_required"],
                "policy_rule_applied": djm["policy_rule_applied"],
            }
        )
        append_reasoning_entry(
            {
                "type": "policy.reasoning.select",
                "target": decision["target"],
                "risk_class": decision["risk_class"],
                "selected_tool": decision["tool"],
                "human_required": decision["human_required"],
                "djm": djm,
            }
        )
    except Exception as exc:
        raise RuntimeError(f"policy_audit_write_failed:{exc}") from exc

    return decision


def _human_required_message(domain: str, action_name: str) -> str:
    return (
        f"Policy Restriction: The domain {domain} is classified as Protected. "
        f"Headless automation is blocked to prevent detection/lockout. "
        f"Please {action_name} manually and let me know when complete."
    )


def _is_headless_requested(tool: str) -> bool:
    return tool.upper() in HEADLESS_TOOLS


def _increment_authenticated_retry(memory: Dict[str, Any], session_id: str) -> int:
    rows = memory.setdefault("authenticated_retry_sessions", {})
    count = int(rows.get(session_id, 0)) + 1
    rows[session_id] = count
    return count


def _emit_human_escalation(decision: Dict[str, Any], constraint: str) -> None:
    # Use domain from rationale or DJM for consistency
    domain = str(decision.get("sense", {}).get("domain") or "unknown-domain")
    target = str(decision.get("target") or domain)
    action_name = str(decision.get("next_steps", ["Perform Action"])[0] or "Perform Action")
    directive = _human_required_message(domain, action_name)
    human_justification = str(decision.get("djm", {}).get("human_justification") or "")

    append_event(
        {
            "type": "human.escalate",
            "category": "policy",
            "Intent": str(decision.get("rationale") or "policy_escalation"),
            "Target": target,
            "Constraint": constraint,
            "Directive": directive,
            "human_justification": human_justification,
        }
    )
    # Keep backward-compatible Phase 2 event too.
    append_event(
        {
            "type": "policy.human_escalation.requested",
            "category": "policy",
            "risk_class": decision.get("risk_class"),
            "domain": domain,
            "message": directive,
            "human_justification": human_justification,
        }
    )


def enforce_before_execute(
    decision: Dict[str, Any],
    execution_tool: Optional[str] = None,
    wait_for_human: bool = False,
    human_timeout_sec: int = 600,
) -> Dict[str, Any]:
    risk = str(decision.get("risk_class", ""))
    selected = str(decision.get("tool", "BLOCKED"))
    requested = (execution_tool or selected).upper()
    domain = str(decision.get("sense", {}).get("domain") or "").lower()

    append_event(
        {
            "type": "policy.act",
            "category": "policy",
            "risk_class": risk,
            "selected_tool": selected,
            "requested_tool": requested,
        }
    )

    if not decision.get("sense"):
        _append_violation("sense_missing_precondition", decision=decision, requested_tool=requested)
        return {"allowed": False, "message": "sense precondition missing"}

    memory = load_policy_memory()

    if risk == "Protected" and requested != "HUMAN_BROWSER":
        _append_violation("protected_headless_forbidden", decision=decision, requested_tool=requested)
        _emit_human_escalation(decision, constraint="Protected domain requires human browser")
        return {"allowed": False, "message": "BLOCKED_BY_POLICY: protected domain"}

    if risk == "Authenticated" and not bool(decision.get("credentials_present", False)) and requested != "HUMAN_BROWSER":
        _append_violation("authenticated_missing_credentials", decision=decision, requested_tool=requested)
        _emit_human_escalation(decision, constraint="Credentials missing for authenticated target")
        return {"allowed": False, "message": "BLOCKED_BY_HUMAN"}

    if domain and _is_confirmed_protected(memory, domain) and _is_headless_requested(requested):
        _append_violation("automation_freeze_confirmed_protected", decision=decision, requested_tool=requested)
        _emit_human_escalation(decision, constraint="Automation freeze active for confirmed protected domain")
        return {"allowed": False, "message": "BLOCKED_BY_POLICY: automation freeze"}

    if risk == "Authenticated" and requested in AUTOMATION_TOOLS and requested != "HUMAN_BROWSER":
        session_id = str(decision.get("session_id") or "default")
        attempts = int(memory.get("authenticated_retry_sessions", {}).get(session_id, 0))
        if attempts >= 1:
            _append_violation("authenticated_retry_limit_exceeded", decision=decision, requested_tool=requested)
            return {"allowed": False, "message": "BLOCKED_BY_POLICY: retry limit"}
        _increment_authenticated_retry(memory, session_id)
        write_policy_memory_atomic(memory)

    if bool(decision.get("human_required")):
        _emit_human_escalation(decision, constraint="Human-in-the-loop required by policy")
        if wait_for_human:
            deadline = time.time() + max(1, int(human_timeout_sec))
            while time.time() < deadline:
                time.sleep(0.05)
            append_event(
                {
                    "type": "human.escalate.timeout",
                    "category": "policy",
                    "status": "BLOCKED_BY_HUMAN",
                    "timeout_sec": int(human_timeout_sec),
                }
            )
        return {"allowed": False, "message": "BLOCKED_BY_HUMAN"}

    return {"allowed": True}


def _update_protected_domain(memory: Dict[str, Any], domain: str, bot_detected: bool) -> Dict[str, Any]:
    rows = memory.setdefault("protected_domains", [])
    now = _utc_now()
    now_epoch = _epoch_now()
    record = _protected_record(memory, domain)
    if not record:
        record = {
            "domain": domain,
            "state": "TENTATIVE",
            "hits": 0,
            "last_blocked": now,
            "frozen": False,
            "detections": [],
        }
        rows.append(record)

    if bot_detected:
        record["hits"] = int(record.get("hits", 0)) + 1
        record["last_blocked"] = now
        detections = [int(x) for x in record.get("detections", []) if isinstance(x, (int, float))]
        detections.append(now_epoch)
        last_24h = [t for t in detections if now_epoch - t <= 24 * 3600]
        record["detections"] = last_24h
        if len(last_24h) >= 2:
            record["state"] = "CONFIRMED"
            record["frozen"] = True
        else:
            record["state"] = "TENTATIVE"
    return record


def reflect_update_policy(decision: Dict[str, Any], outcome: Dict[str, Any], policy_memory: Dict[str, Any]) -> Dict[str, Any]:
    updated = json.loads(json.dumps(policy_memory))
    domain = str(outcome.get("domain") or decision.get("sense", {}).get("domain") or "").strip().lower()
    status = int(outcome.get("status", 0))
    headers = {str(k).lower(): str(v).lower() for k, v in (outcome.get("headers") or {}).items()}

    append_event(
        {
            "type": "policy.reflect",
            "category": "policy",
            "domain": domain,
            "status": status,
        }
    )

    has_audit_failure = bool(outcome.get("audit_failed"))
    if has_audit_failure and str(outcome.get("result") or "").lower() in {"success", "ok"}:
        _append_violation("hallucinated_success_rollback", decision=decision)
        return updated

    has_evidence = bool(outcome.get("evidence")) or status in {403, 429}
    if not has_evidence:
        append_event(
            {
                "type": "policy.reflect.discarded",
                "category": "policy",
                "reason": "learning_without_evidence",
                "domain": domain,
            }
        )
        return updated

    if domain and 200 <= status < 300:
        existing = _protected_record(updated, domain)
        if existing and str(existing.get("state", "")).upper() == "TENTATIVE":
            rows = updated.get("protected_domains", [])
            updated["protected_domains"] = [
                row for row in rows if str(row.get("domain", "")).lower() != domain
            ]
            write_policy_memory_atomic(updated)
            append_event(
                {
                    "type": "policy.reflect.updated",
                    "category": "policy",
                    "domain": domain,
                    "status": status,
                    "updates": [{"op": "remove_tentative_domain_after_verified_success", "domain": domain}],
                }
            )
            return updated

    bot_detected = status in {403, 429} and _has_protection_header(headers)

    updates: List[Dict[str, Any]] = []
    if domain and bot_detected:
        record = _update_protected_domain(updated, domain, bot_detected=True)
        updates.append(
            {
                "op": "update_outcome",
                "domain": domain,
                "state": record.get("state"),
                "hits": int(record.get("hits", 0)),
            }
        )

    updated.setdefault("outcomes", []).append(
        {
            "ts": _utc_now(),
            "domain": domain,
            "status": status,
            "tool": decision.get("tool"),
            "risk_class": decision.get("risk_class"),
            "headers": headers,
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


def remove_protected_domain(domain: str, evidence: Optional[Dict[str, Any]] = None) -> bool:
    evidence = evidence or {}
    manual_verified = bool(evidence.get("manual_verification")) and bool(evidence.get("reflect_event_ref"))
    if not manual_verified:
        _append_violation("remove_protected_domain_without_verification", requested_tool="")
        return False

    memory = load_policy_memory()
    rows = memory.get("protected_domains", [])
    kept = [row for row in rows if str(row.get("domain", "")).lower() != domain.lower()]
    if len(kept) == len(rows):
        return False
    memory["protected_domains"] = kept
    write_policy_memory_atomic(memory)
    append_event(
        {
            "type": "policy.reflect.updated",
            "category": "policy",
            "updates": [{"op": "remove_protected_domain", "domain": domain}],
        }
    )
    return True


def emit_policy_verified_if_proven(actor: str = "Auditor", phase: str = "2.1") -> bool:
    memory = load_policy_memory()
    events = []
    if EVENTS_PATH.exists():
        for line in EVENTS_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                events.append(row)

    chain_types = {"policy.sense.started", "policy.reasoning.select", "policy.act", "policy.reflect.updated"}
    seen_chain = {row.get("type") for row in events}
    chain_ok = chain_types.issubset(seen_chain)

    has_human_escalate = any(row.get("type") == "human.escalate" for row in events)
    has_violation = any(row.get("type") == "policy.violation" for row in events)

    reasoning_rows = load_reasoning_entries()
    reasoning_ok = len(reasoning_rows) > 0 and all("djm" in row for row in reasoning_rows)

    if chain_ok and has_human_escalate and has_violation and reasoning_ok:
        append_event(
            {
                "type": "policy.verified",
                "category": "policy",
                "phase": phase,
                "actor": actor,
                "proof": {
                    "reasoning_path": str(REASONING_AUDIT_PATH),
                    "events_path": str(EVENTS_PATH),
                    "chain_types": sorted(chain_types),
                    "reasoning_entries": len(reasoning_rows),
                    "protected_domains": len(memory.get("protected_domains", [])),
                },
            }
        )
        return True
    return False
