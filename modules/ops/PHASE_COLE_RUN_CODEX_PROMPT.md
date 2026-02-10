# Codex Prompt — Cole-Run Integration

Implement `cole_run` as first-class read-only tool.

Scope-lock files:
- `cole/tools/cole_run.zsh`
- `tools/run_tool.zsh`
- `core_brain/catalog/registry.yaml`
- `modules/ops/*.md` docs listed in task
- `core/verify/test_cole_run_integration.py`

Non-goals:
- no code changes outside listed files
- no execution authority additions
- no network calls
- no writes except stdout
