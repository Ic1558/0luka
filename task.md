# Task: Install and Configure NotebookLM MCP

## Status
- [x] Discovery
- [x] Plan Approval
- [x] Infrastructure Upgrade (Lisa upgraded to v2 via `lisa_executor.py` edit)
- [x] Installation (Delegated to Lisa `install_force_mcp`, success)
- [x] Configuration (Updated `opencode.json` with correct binary path)
- [x] Authentication Attempt (Delegated to Lisa `auth_notebooklm`)
  - **Result**: Failed (Chrome 403 Forbidden).
  - **Reason**: `notebooklm-mcp-auth` auto-mode requires closing Chrome or manual interaction impossible in background.
  - **Next Step**: User must run auth manually or use `--file` mode.
- [x] Verification (Server binary exists and is executable)

## Details
- **Installed Version**: 0.1.15
- **Location**: `/opt/homebrew/bin/notebooklm-mcp`
- **Config**: Pointed to `/opt/homebrew/bin/notebooklm-mcp`.

- [x] Skill Documentation (Created `skills/notebooklm/SKILL.md`)

## User Action Required
- Run `notebooklm-mcp-auth` in terminal to complete authentication.
- Access the `notebooklm` skill via the agent for high-level research tasks.
