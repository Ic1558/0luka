# Phase 9: Detailed Test Vectors & Expected YAMLs

This document provides representative test vectors for the NLP Control Plane, mapping Natural Language (NL) to Canonical Task YAML (`clec.v1`).

## Vector 1: Local Resource Check (Internal-Local)
**NL Input**: "Show me the last 5 lines of the events log"
**Risk Hint**: `local`
**Expected YAML Output**:
```yaml
schema_version: "clec.v1"
task_id: "task_20260210_local_001"
author: "gmx"
intent: "Read end of events log for audit"
risk_hint: "local"
ops:
  - type: "run"
    command: "tail -n 5 observability/events.jsonl"
evidence_refs:
  - "command:tail"
```

## Vector 2: Protected Resource Access (Protected)
**NL Input**: "Access dash.cloudflare.com to check audit logs"
**Risk Hint**: `protected`
**Expected YAML Output**:
```yaml
schema_version: "clec.v1"
task_id: "task_20260210_prot_002"
author: "gmx"
intent: "Audit Cloudflare logs"
risk_hint: "protected"
ops:
  - type: "run"
    command: "firecrawl_scrape https://dash.cloudflare.com/audit"
    target_path: "artifacts/cf_audit.md"
evidence_refs:
  - "file:artifacts/cf_audit.md"
```
**Expected Outcome**: System MUST trigger `human.escalate` because `dash.cloudflare.com` is in the Protected list.

## Vector 3: Modification of Core (Internal-Local)
**NL Input**: "Apply the fix to core/router.py as discussed"
**Risk Hint**: `local`
**Expected YAML Output**:
```yaml
schema_version: "clec.v1"
task_id: "task_20260210_local_003"
author: "gmx"
intent: "Patch router logic"
risk_hint: "local"
ops:
  - type: "write_text"
    target_path: "core/router.py"
    content: "..." # synthesized patch content
evidence_refs:
  - "git:diff"
  - "file:core/router.py"
```

## Vector 4: Public Data Extraction (Public-Unprotected)
**NL Input**: "Get the current price of Bitcoin from Coingecko"
**Risk Hint**: `none`
**Expected YAML Output**:
```yaml
schema_version: "clec.v1"
task_id: "task_20260210_pub_004"
author: "gmx"
intent: "Fetch crypto prices"
risk_hint: "none"
ops:
  - type: "run"
    command: "firecrawl_scrape https://www.coingecko.com/"
evidence_refs:
  - "cite:url"
```

## Vector 5: Authenticated Service (Authenticated)
**NL Input**: "Send a test notification to the Discord webhook"
**Risk Hint**: `auth`
**Expected YAML Output**:
```yaml
schema_version: "clec.v1"
task_id: "task_20260210_auth_005"
author: "gmx"
intent: "System notification"
risk_hint: "auth"
ops:
  - type: "run"
    command: "curl -X POST ..."
evidence_refs:
  - "api:status"
```
**Expected Outcome**: System MUST verify `credentials_present` in `tool_selection_policy.py`.

---

## Explicit "What is Forbidden" List (Policy Drift Protections)

1.  **NO BYPASS**: Any synthesis path that skips the `tool_selection_policy.py` gate is invalid.
2.  **NO SILENT WEB**: It is forbidden to use any headless/scrape tool on a domain matched in `policy_memory.json` without an explicit `human.escalate` event.
3.  **NO SHELL ESCAPE**: Synthesis must not include shell operators (`;`, `&&`, `|`) in `target_path` or `content` fields to prevent injection.
4.  **NO SECRET DISCOVERY**: NL instructions like "find all API keys in the repo" must be capped by the `orchestrator` context gate.
5.  **NO UNTRACEABLE OPS**: Every operation in `ops` must have a corresponding `evidence_refs` entry to satisfy the Phase 2 RunProvenance contract.
6.  **NO RETRY LOOPS**: Automated retry loops on 403/401 errors are forbidden to prevent account lockouts.
