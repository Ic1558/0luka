# Phase Cole-Run Plan

1. Implement `cole/tools/cole_run.zsh` with `list|latest|show` only.
2. Wire `tools/run_tool.zsh` case `cole-run` to delegate strictly to `cole_run.zsh`.
3. Register `cole_run` in `core_brain/catalog/registry.yaml` with read-only caps.
4. Add integration tests for:
   - deterministic list ordering
   - latest rule
   - show path scope guard
   - no write/network patterns
5. Run verification:
   - `python3 -m pytest core/verify -q`
   - `python3 core/health.py --full`
