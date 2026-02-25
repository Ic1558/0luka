# Debt Audit: Contracts vs State
- scope: audit-only (no code changes, no launchctl)

## Classification Table
| Target | Classification | Proof | Recommendation |
|---|---|---|---|
| `core/schemas/v1/job_record.json` | Paper Spec (NOT ENFORCED) | No XREF hits for literal `job_record.json` outside self/docs; no runtime loader found. | Keep+Wire or Deprecate: move to docs/contracts with `STATUS: PAPER_SPEC`, or wire into runtime validation with tests. |
| `core/schemas/v1/task_spec_v1.yaml` | Paper Spec (ORPHAN PATH) | Consumer points to missing `core/schema/task_spec_v1.yaml` while file lives at `core/schemas/v1/task_spec_v1.yaml`. | Move+Wire: choose one canonical path and enforce with tests; until then mark PAPER_SPEC. |
| `core/semantics/job_lifecycle.md` | Paper Spec (NOT MACHINE-ENFORCED) | Referenced by docs/OpenAPI description and markdown `$ref`; no parser/enforcer usage found. | Keep as docs contract with status header, or convert to machine-readable transitions and enforce. |
| `core/state/policy_memory.json` | Mutable State (Executable + Writable in repo) | `core/tool_selection_policy.py` reads/writes the file via `POLICY_MEMORY_PATH`. | Move mutable state to runtime root via `LUKA_RUNTIME_ROOT` + bootstrap migration; keep contract/spec in repo. |

## Command Output: XREF Sweep
Command:
```bash
rg -n --hidden --glob '!**/.git/**' "job_record\.json|job_lifecycle\.md|task_spec_v1\.yaml|policy_memory\.json|core/schemas/v1|core/semantics|core/state" /Users/icmini/0luka
```
Output:
```text
/Users/icmini/0luka/plans/core_architecture_phased.md:90:│   ├── job_lifecycle.md
/Users/icmini/0luka/plans/core_architecture_rust.md:86:│   ├── job_lifecycle.md         # Generated from Rust
/Users/icmini/0luka/tools/bridge/bridge_consumer.py:224:        schema=root / "core/schema/task_spec_v1.yaml",
/Users/icmini/0luka/core/tool_selection_policy.py:13:POLICY_MEMORY_PATH = ROOT / "core" / "state" / "policy_memory.json"
/Users/icmini/0luka/modules/nlp_control_plane/VECTORS.md:100:2.  **NO SILENT WEB**: It is forbidden to use any headless/scrape tool on a domain matched in `policy_memory.json` without an explicit `human.escalate` event.
/Users/icmini/0luka/modules/nlp_control_plane/PHASE9_SPEC.md:56:3. **Silent Web Access**: Using `curl`, `requests`, or `headless_browser` on domains matched against the `policy_memory.json` Protected list without escalation.
/Users/icmini/0luka/core/contracts/v1/opal_api.openapi.json:149:        "description": "Deterministic state of the job. See core/semantics/job_lifecycle.md for rules.",
/Users/icmini/0luka/core/schemas/v1/job_record.json:18:            "$ref": "../semantics/job_lifecycle.md#/states"
/Users/icmini/0luka/core/schemas/v1/task_spec_v1.yaml:2:# Path: core/schema/task_spec_v1.yaml
```

## Command Output: Runtime Write Proof (`policy_memory.json`)
Command:
```bash
ls -la core/state/policy_memory.json
```
Output:
```text
-rw-r--r--@ 1 icmini  staff  187 Feb 25 06:49 core/state/policy_memory.json
```

Command:
```bash
stat -f "%m %N" core/state/policy_memory.json
```
Output:
```text
1771976959 core/state/policy_memory.json
```

Command:
```bash
lsof | rg "policy_memory\.json" || true
```
Output:
```text
```

## Command Output: Focused XREF per Target
Command:
```bash
rg -n --hidden --glob '!**/.git/**' "job_record\.json" /Users/icmini/0luka || echo no_matches
```
Output:
```text
no_matches
```

Command:
```bash
rg -n --hidden --glob '!**/.git/**' "task_spec_v1\.yaml|core/schema/task_spec_v1\.yaml|core/schemas/v1/task_spec_v1\.yaml" /Users/icmini/0luka
```
Output:
```text
/Users/icmini/0luka/core/schemas/v1/task_spec_v1.yaml:2:# Path: core/schema/task_spec_v1.yaml
/Users/icmini/0luka/tools/bridge/bridge_consumer.py:224:        schema=root / "core/schema/task_spec_v1.yaml",
```

Command:
```bash
rg -n --hidden --glob '!**/.git/**' "job_lifecycle\.md|core/semantics/job_lifecycle\.md" /Users/icmini/0luka
```
Output:
```text
/Users/icmini/0luka/plans/core_architecture_phased.md:90:│   ├── job_lifecycle.md
/Users/icmini/0luka/plans/core_architecture_rust.md:86:│   ├── job_lifecycle.md         # Generated from Rust
/Users/icmini/0luka/core/schemas/v1/job_record.json:18:            "$ref": "../semantics/job_lifecycle.md#/states"
/Users/icmini/0luka/core/contracts/v1/opal_api.openapi.json:149:        "description": "Deterministic state of the job. See core/semantics/job_lifecycle.md for rules.",
```

Command:
```bash
rg -n --hidden --glob '!**/.git/**' "policy_memory\.json|POLICY_MEMORY_PATH" /Users/icmini/0luka
```
Output:
```text
/Users/icmini/0luka/core/tool_selection_policy.py:13:POLICY_MEMORY_PATH = ROOT / "core" / "state" / "policy_memory.json"
/Users/icmini/0luka/core/tool_selection_policy.py:60:    if not POLICY_MEMORY_PATH.exists():
/Users/icmini/0luka/core/tool_selection_policy.py:65:        data = json.loads(POLICY_MEMORY_PATH.read_text(encoding="utf-8"))
/Users/icmini/0luka/core/tool_selection_policy.py:80:    POLICY_MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
/Users/icmini/0luka/core/tool_selection_policy.py:83:    tmp = POLICY_MEMORY_PATH.parent / ".policy_memory.tmp"
/Users/icmini/0luka/core/tool_selection_policy.py:85:    tmp.replace(POLICY_MEMORY_PATH)
/Users/icmini/0luka/modules/nlp_control_plane/VECTORS.md:100:2.  **NO SILENT WEB**: It is forbidden to use any headless/scrape tool on a domain matched in `policy_memory.json` without an explicit `human.escalate` event.
/Users/icmini/0luka/modules/nlp_control_plane/PHASE9_SPEC.md:56:3. **Silent Web Access**: Using `curl`, `requests`, or `headless_browser` on domains matched against the `policy_memory.json` Protected list without escalation.
```

Command:
```bash
ls -la core/schema 2>/dev/null || echo 'core/schema missing' && ls -la core/schemas/v1
```
Output:
```text
core/schema missing
total 16
drwxr-xr-x@ 4 icmini  staff   128 Feb  7 02:32 .
drwxr-xr-x@ 3 icmini  staff    96 Feb  5 03:18 ..
-rw-r--r--@ 1 icmini  staff  2568 Feb  7 02:32 job_record.json
-rw-r--r--@ 1 icmini  staff   892 Feb  5 03:18 task_spec_v1.yaml
```
