# Chat Control Plane Specification v1.0

> **Status**: PROPOSED → APPROVED
> **Author**: GMX | **Analyst**: CLC
> **System**: 0luka | **Mode**: chat_first

---

## 1. Purpose

Enable natural language interaction with 0luka without:
- Building a frontend UI
- Modifying the execution plane
- Compromising governance

---

## 2. Invariants (Non-Negotiable)

```yaml
invariants:
  - name: no_gateway_execution
    rule: "Gateway MUST NOT execute tools/scripts/subprocess"
    enforcement: static_audit

  - name: explicit_confirm
    rule: "No task creation without explicit 'confirm' action"
    enforcement: api_contract

  - name: single_author
    rule: "All tasks authored as 'gmx' (server-injected)"
    enforcement: model_field

  - name: execution_unchanged
    rule: "bridge_consumer.py and Lisa unchanged"
    enforcement: git_diff_check

  - name: forensic_trace
    rule: "All gateway operations logged to telemetry"
    enforcement: vera_audit
```

---

## 3. API Contract

### 3.1 Preview

```yaml
endpoint: POST /api/v1/chat/preview
request:
  raw_input: string        # Natural language input
  channel: string          # "terminal" | "telegram"
  session_id: string       # Client-generated UUID

response:
  preview_id: string       # Server-generated, expires in TTL
  normalized_task:
    task_id: string        # Proposed task ID
    intent: string         # Parsed intent
    operations: array      # Structured operations
    risk: string           # "low" | "high"
    lane: string           # "fast" | "approval"
  requires_confirm: true
  ttl_seconds: 300
```

### 3.2 Confirm

```yaml
endpoint: POST /api/v1/chat/confirm
request:
  preview_id: string       # From preview response
  session_id: string       # Must match preview session

response:
  status: "ok" | "error"
  task_id: string          # Final task ID
  path_written: string     # interface/inbox/task_*.yaml
  ack: string              # Human-readable confirmation
```

### 3.3 Watch

```yaml
endpoint: GET /api/v1/chat/watch/{task_id}
request:
  session_id: string       # Query param

response:
  task_id: string
  state: string            # accepted|pending_approval|running|done|failed
  last_event: object       # Latest telemetry event
  result_summary: string   # If done, summary of result
  updated_at: string       # ISO timestamp
```

---

## 4. Session Contract

```yaml
session:
  id: uuid4
  channel: string
  created_at: iso8601
  ttl_seconds: 600
  preview_cache: map<preview_id, TaskSpec>

lifecycle:
  - created: on first /preview
  - active: TTL resets on each request
  - expired: after TTL with no activity
  - destroyed: explicit cleanup or TTL

rules:
  - preview_id valid only within session
  - cross-session confirm rejected
  - max 5 pending previews per session
```

---

## 5. NLP Normalization Rules (v1 Deterministic)

```yaml
patterns:
  - pattern: "liam (check|show) status"
    intent: "status_check"
    tool: "status_reader"
    risk: low

  - pattern: "liam session (start|begin)"
    intent: "session_start"
    tool: "session_manager"
    risk: low

  - pattern: "lisa (run|execute) {task}"
    intent: "task_execution"
    tool: "task_runner"
    risk: high

  - pattern: "show (tasks|pending|inbox)"
    intent: "task_list"
    tool: "inbox_reader"
    risk: low

fallback:
  intent: "unknown"
  tool: "unknown"
  risk: high
  requires_structured_override: true
```

---

## 6. Security Model

### 6.1 Write Scope

```python
ALLOWED_WRITE_PATHS = [
    "interface/inbox/",
    "interface/pending_approval/",
    "observability/telemetry/gateway.jsonl"
]

FORBIDDEN_WRITE_PATHS = [
    "core/",
    "core_brain/",
    "runtime/",
    ".env*"
]
```

### 6.2 Execution Prevention

```python
# Gateway code MUST NOT contain:
FORBIDDEN_PATTERNS = [
    "subprocess",
    "os.system",
    "os.exec",
    "eval(",
    "exec(",
    "__import__"
]

# Vera audit script:
# grep -rE "(subprocess|os\.system|os\.exec|eval\(|exec\()" tools/web_bridge/
# Expected output: 0 matches
```

---

## 7. Telemetry Schema (gateway.jsonl)

```json
{
  "ts_utc": "2026-02-02T10:00:00Z",
  "module": "chat_gateway",
  "event": "preview|confirm|watch",
  "session_id": "uuid",
  "channel": "terminal|telegram",
  "preview_id": "uuid",
  "task_id": "task_*",
  "raw_input": "liam check status",
  "normalized_intent": "status_check",
  "risk": "low",
  "outcome": "ok|error",
  "latency_ms": 45
}
```

---

## 8. Error Handling

```yaml
errors:
  - code: PREVIEW_EXPIRED
    message: "Preview has expired, please re-preview"
    action: return_to_preview

  - code: SESSION_MISMATCH
    message: "Session ID does not match preview"
    action: reject_confirm

  - code: TASK_COLLISION
    message: "Task ID already exists"
    action: regenerate_id_retry

  - code: SCHEMA_INVALID
    message: "Normalized task failed schema validation"
    action: return_error_with_details

  - code: RATE_LIMITED
    message: "Too many requests, wait {n} seconds"
    action: 429_response
```

---

## 9. Implementation Checklist

### Phase 1: Gateway Core
- [ ] `session_store.py` - In-memory session management
- [ ] `preview_cache.py` - Preview ID → TaskSpec mapping
- [ ] `routers/chat.py` - /preview, /confirm, /watch
- [ ] `nlp/normalizer.py` - Rule-based parser

### Phase 2: Terminal CLI
- [ ] `chatctl.zsh` - Interactive terminal client
- [ ] Preview display formatting
- [ ] Confirm prompt (y/n)
- [ ] Watch polling loop

### Phase 3: Governance
- [ ] Gateway telemetry logging
- [ ] Vera audit hook
- [ ] Static analysis script

### Phase 4: Telegram (Deferred)
- [ ] Kim bot integration
- [ ] Confirm via reply
- [ ] State notifications

---

## 10. Approval Record

```yaml
proposed_by: gmx
proposed_at: 2026-02-02
analyzed_by: clc
analysis_score: 82/100
status: APPROVED_FOR_IMPLEMENTATION
implementation_start: pending_boss_approval
```
