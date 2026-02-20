# Workstream: B1 - Inbox Hygiene (04_B1)

## 1. Goal

Ensure the dispatcher gracefully handles and isolates malformed inputs to prevent control plane crashes.

## 2. Policy/DoD

- Malformed YAML (syntax error) -> **QUARANTINE**.
- Non-Object YAML (e.g., list or string input) -> **QUARANTINE**.
- No crash allowed in supervisor loop.

## 3. Steps

1. Insert error handler in `core/task_dispatcher.py`'s file reader.
2. Define `quarantine/` directory in `interface/inbox/`.
3. Emit linter warning on every quarantine event.

## 4. Verify

- **Injection A:** `malformed_syntax_test.yaml` (Invalid YAML characters).
- **Injection B:** `malformed_object_test.yaml` (Valid YAML but not a dictionary).
- **Result:** Both files moved to quarantine; control plane continues running.

## 5. Evidence

- **Proof Pack:** `20260220T192226Z_b1_inbox_hygiene`
- **Verification Log:** `/observability/artifacts/proof_packs/20260220T192226Z_b1_inbox_hygiene/verification_notes.txt`
