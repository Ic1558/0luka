# Walkthrough: WO-14A / PHASE 2 (NotebookLM External Publish Gate) & Registry Fix

**Objective**: Complete the remaining tasks from PR-2 (NotebookLM Publish Gate) and the WO-3E-REGISTRYFIX to ensure machine-readability of the Phase 3E governance status.

## Execution Steps

### Part 1: WO-3E-REGISTRYFIX

1. **Identified Error**: Found that `core/governance/phase_status.yaml` previously lacked a formally instantiated top-level structure or explicit definition for `PHASE_3E`.
2. **Corrected Schema**: Instantiated `PHASE_3E` with exactly the appropriate `IMPLEMENTED` state, mapped the `last_verified_ts` appropriately, and assigned `commit_sha` to the verifiable introduction of the feature. `requires` references were safely enumerated based on prior class completions.
3. **Verified File Lock**: Executed `python3 tools/ops/governance_file_lock.py --build-manifest --verify-manifest` validating the schema change smoothly.
4. **Verified Extractability**:

   ```python
   d=yaml.safe_load(p.read_text())
   print(d.get("PHASE_3E"))
   # {'state': 'IMPLEMENTED', 'requires': [...], 'last_verified_ts': ..., 'commit_sha': '843d7e2', 'evidence_path': 'core_brain/agents/tests'}
   ```

5. **Committed**: Handled cleanly in PR-3E-REGISTRYFIX and successfully propagated.

### Part 2: WO-14A PR-2 (Class B)

1. **Built `tools/ops/publish_notebooklm.py` (External Gate)**:
   - Evaluated four hard constraints before triggering any behavior:
     - Workspace cleanliness (`git status`)
     - SOT pack symlink sanity (latest pack exists).
     - Manifest integrity (`pack_sha256` matching `git_head` metadata).
     - Activity log proof constraint (`sot_seal` present in feed mapping exactly to the `pack_sha256` requested).
   - Applied concurrency locking via `latest/.sync_lock` during publish.
   - Wrote metadata blob to telemetry output file `observability/telemetry/sot_publish.json`.
   - Wrote explicit egress event `action: "sot_publish"` successfully into `observability/logs/activity_feed.jsonl` matching the required structure.
2. **Mocked the Target Layer**:
   - Implemented `upload_to_notebooklm(pack_path)` which mocks the call to the actual MCP system since we constrain R2/MED tests locally.
3. **Rigorous Test Validation**:
   - Completed `core/verify/test_publish_notebooklm_gate.py` implementing `pytest` suites mimicking full environments to assert gating and dirty-handling conditions gracefully.
   - Verified tests `pass` independently.
4. **Resolved Git Ignored Leaks**:
   - `observability/telemetry/*.json` was explicitly ignored natively in the `.gitignore` baseline preventing telemetry dirtying the index.

## Final Result

- Both issues successfully fulfilled.
- Both test groups and linter passes.
- PRs merged back into main transparently maintaining Phase 14 integrity objectives natively satisfying the external publish constraints (Class B/Type R2/MED).
