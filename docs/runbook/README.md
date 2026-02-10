# 0luka Runbook

This directory contains operational procedures and checklists for 0luka automation.

## Runtime Requirements

### Librarian Automation
Librarian requires the following runtime dependencies:

- **Python 3.x** (standard library)
- **PyYAML** (for YAML parsing)
  - Installation: `pip install pyyaml`
  - Required for: `librarian plan` and `librarian apply` state file parsing

## Procedures

### Librarian Workflow
1. `librarian plan` - Scan scatter, create move plan in `state/pending.yaml`
2. `librarian apply` - Execute moves, update audit, reindex, update summary
3. `librarian score` - Evaluate action against policy (future)
4. `librarian refresh` - Update state, reindex, regenerate summary (future)

## SOT Pointers

- Human Dashboard: `luka.md`
- Machine State: `state/current_system.json`, `state/pending.yaml`, `state/recent_changes.jsonl`
- Component Logs: `logs/components/<component>/current.log`
- Summary Latest: `reports/summary/latest.md`

## Browser Operator (External)

Run the worker (polls inbox and executes tasks via Selenium + Chrome):

```bash
python3 tools/external/browser_operator_worker.py
```

Notes:
- Safe mode uses an isolated Chrome profile at `runtime/browser_operator_profile` (default headless).
- Privileged mode (`attach_user_chrome`) expects a dedicated Chrome debug instance started with `--remote-debugging-port=9222` and will attach via `BROWSER_OP_DEBUGGER_ADDRESS` (default `127.0.0.1:9222`). Do not attach to your normal profile without a debug instance.
- Optional env flags: `BROWSER_OP_HEADLESS=0` to show the bot-profile browser window.
