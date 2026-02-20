# Implementation Plan: WO-14A / PHASE 1 (Internal SOT Pack Builder)

**Mission**: Implement a governance-safe SOT synchronization boundary. Phase 1 focuses purely on the Internal SOT Pack Builder (`Class A`), ensuring it is atomic, seal-anchored, fail-closed, and has zero external egress. No background automation. No embedded STATE in tracked files.

## Definition of Done (PR-1)

1. `tools/ops/build_sot_pack.py` creates a valid pack atomically in `observability/artifacts/sot_packs/{ts}_{shortsha}` and updates `latest` pointer.
2. The pack contains `0luka.md`, latest `_snapshot.md`, catalog index (`tools/catalog_lookup.zsh`), `manifest.json`, and `sha256sums.txt`.
3. The activity feed (`observability/stl/ledger/activity_feed.jsonl`) contains the `sot_seal` event.
4. `activity_feed_linter` passes.
5. Builder aborts if the Git tree is dirty or HEAD does not match the latest verified activity feed commit (Seal Proof Chain Validation).
6. Uses a `.build_lock` temporary file for an Anti-Race Guard during pack generation.
7. Git status is entirely clean after the run (no tracked files modified).
8. No references to NotebookLM in the codebase.

## Execution Steps

1. **Pre-Checks**: Validate repository state (using `git log`, `git status`). Extract last verified activity feed commit.
2. **Develop `tools/ops/build_sot_pack.py`**:
   - Implement `check_preconditions()` ensuring Git working tree is clean and un-modified. Ensure HEAD matches the most recent verified commit in `activity_feed.jsonl`.
   - Implement temporary dot lock file inside `observability/artifacts/sot_packs/.build_lock`. Fail if exists.
   - Assemble `0luka.md`, latest `observability/artifacts/snapshots/*_snapshot.md`, `tools/catalog_lookup.zsh`, minimal docs like `docs/notebooklm_publish_design.md`.
   - Hash (SHA-256) all files.
   - Construct `manifest.json` and `sha256sums.txt`.
   - Generate SOT Pack zip or folder and perform atomic `os.rename()` from `staging` to `sot_packs/<pack>`.
   - Update `latest` symlink.
   - Emit `sot_seal` to `activity_feed.jsonl`.
3. **Develop `core/verify/test_build_sot_pack.py`**:
   - Verify builder aborts if git tree dirty.
   - Verify builder creates pack successfully if clean.
   - Verify manifest exists and hashes match.
   - Verify `activity_feed` contains a seal event.
   - Verify tracked tree is perfectly clean post run.
4. **Dry Run**: Execute `pytest core/verify/test_build_sot_pack.py -q`. Wait and review any failures to correct logic.
5. **Verify**: Execute the full Proof Pack commands and generate `walkthrough.md`.
