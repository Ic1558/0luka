# Phase 9: NLP Control Plane Specification

**Version**: 1.0  
**Status**: Authoritative Spec  
**Author**: GMX (System Auditor & Architect)  
**Baseline**: Phase 2 (Evidence Enforcement) + Phase 2.1 (Governance Reasoning)  

## 1. Objective
Enable a natural language interface for the 0luka system that maintains strict governance, reasoning (DJM), and provenance. Phase 9 converts natural language (NL) instructions into canonical, verifiable Task YAMLs before execution.

---

## 2. System Architecture (Implementation Lane)

The NLP Control Plane consists of three core components:
1. **Linguist (NL Synthesis)**: Maps NL strings to `clec.v1` Ops.
2. **Safety Sentry (Risk Detection)**: Identifies `risk_hint` (Internal-Local, Protected, Authenticated).
3. **Execution Pipeline**: Integrates Phase 2/2.1 gates (Fail-Closed).

### 2.1 Canonical Task Schema (`clec.v1`)
All synthesized tasks must adhere to this schema:
```yaml
schema_version: "clec.v1"
task_id: "uuid-v4"
author: "string"      # e.g., gmx, user
intent: "string"      # Clear description of purpose
risk_hint: "string"   # none | protected | auth | local
ops:                  # List of CLEC operations
  - type: "write_text|mkdir|copy|run|read_file"
    target_path: "string"
    content: "string" # for write_text
    command: "string" # for run
evidence_refs: []     # List of required evidence (e.g., git:diff, file:sha256)
```

---

## 3. Governance Integration Rules

### 3.1 Pre-Execution Check (Mandatory Preconditions)
Before any synthesized task is executed via `CLECExecutor`:
1. **Phase 2.1 Gate**: If `risk_hint` is `protected` or `auth`, the system MUST call `sense_target()` and `select_tool()`.
2. **Phase 2 Gate**: MUST call `init_run_provenance()` to generate a deterministic `input_hash` before any side effect occurs.

### 3.2 "No Silent Automation" Policy
* **Human-in-the-Loop**: Headless automation is strictly FORBIDDEN for any domain classified as `Protected` or target requiring user authentication (missing credentials).
* **Escalation Trigger**: Upon detection of a risk signal (e.g., Cloudflare, Login wall), the system MUST emit a `human.escalate` event with an **actionable directive**.
* **Directive Format**: `Please [Login/Solve Challenge/Review Code] manually and let me know when complete.`

---

## 4. Operational Invariants (What Is Forbidden)

1. **Automation Drift**: Bypassing `tool_selection_policy.py` for "efficiency" is a critical violation.
2. **Schema Escape**: Executing tasks that lack `task_id` or `author` fields.
3. **Silent Web Access**: Using `curl`, `requests`, or `headless_browser` on domains matched against the `policy_memory.json` Protected list without escalation.
4. **Credential Leakage**: Putting plain-text secrets in `intent` or `reasoning.jsonl`.
5. **Hallucinated Provenance**: Modifying `input_hash` or `output_hash` manually in the logs.

---

## 5. Test Vectors (NLP Conversion Examples)

| Natural Language Input | Expected `risk_hint` | Expected Ops |
| :--- | :--- | :--- |
| "Check git status in the repo" | `local` | `run: git status` |
| "Read the .env.local file" | `local` | `read_file: .env.local` |
| "Scrape Wikipedia for AI news" | `none` | `run: firecrawl_scrape ...` |
| "Login to dash.cloudflare.com" | `protected` | `HUMAN_BROWSER` (Escalation) |
| "Apply fix to core logic" | `local` | `write_text: core/...` |

---

## 6. Definition of Done (DoD)

1. **[PROVEN]** `observability/events.jsonl` contains the full chain: `policy.sense.started` -> `policy.reasoning.select` -> `human.escalate`.
2. **[PROVEN]** `observability/artifacts/run_provenance.jsonl` contains an entry for every successful NL task with bit-parity hashes.
3. **[PROVEN]** `prove_phase9_nlp.py` passes 100% of test vectors including negative tests (rejection of unauthorized ops).
4. **[PROVEN]** No hardcoded sensitive paths in `intent` or `reasoning.jsonl`.

---

## 7. Minimal Implementation Plan

1. **Step 1**: Create `modules/nlp_control_plane/core/synthesizer.py`.
2. **Step 2**: Integrate `tool_selection_policy.py` into the synthesizer loop.
3. **Step 3**: Implement `CLECExecutor` bridge to handle `clec.v1` output.
4. **Step 4**: Run `prove_phase9_nlp.py` to collect evidence.
