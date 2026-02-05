# Plan: Antigravity Seamless Workflow - Final Steps

## Current State (Verified)

| Component | Status | Location |
|-----------|--------|----------|
| SSH MBP → Mini | ✅ Complete | Alias `icmini` works |
| Reboot test | ✅ Passed | Mini auto-restarts |
| ic1558/core repo | ✅ Exists | https://github.com/ic1558/core |
| OpenAPI contract | ✅ v1.3.0 | `/Users/icmini/0luka/core/contracts/v1/opal_api.openapi.json` |
| OPAL API Server | ✅ Running | `runtime/apps/opal_api/opal_api_server.py` |
| **GET /api/jobs** | ⚠️ GAP | Implemented locally, NOT in contract |
| **Setup menu** | ❌ Missing | Should be at `~/.local/bin/setup` on MBP |

---

## Remaining Tasks (2 Items)

### Task 1: Sync Contract ↔ Implementation

**Problem:** `GET /api/jobs` is implemented in `opal_api_server.py` (line ~80) but missing from `opal_api.openapi.json`.

**Action:**
Add to `/Users/icmini/0luka/core/contracts/v1/opal_api.openapi.json`:

```json
"/api/jobs": {
  "get": {
    "operationId": "listJobs",
    "summary": "List all jobs",
    "description": "Returns all jobs in the system (Minimal Law)",
    "responses": {
      "200": {
        "description": "Map of job_id to JobDetail",
        "content": {
          "application/json": {
            "schema": {
              "type": "object",
              "additionalProperties": {
                "$ref": "#/components/schemas/JobDetail"
              }
            }
          }
        }
      }
    }
  },
  "post": { ... existing ... }
}
```

Then commit the uncommitted changes:
- `runtime/apps/opal_api/opal_api_server.py`
- `core/contracts/v1/opal_api.openapi.json`

---

### Task 2: Create Setup Menu on MBP

**Problem:** No `setup` command exists for quick MBP → Mini control.

**Action:** Create `~/.local/bin/setup` on **MBP** (not Mini):

```bash
#!/bin/zsh
# MBP → Mini Control Panel

echo "┌─────────────────────────────────────┐"
echo "│      MBP → Mini Control Panel       │"
echo "├─────────────────────────────────────┤"
echo "│  1) SSH to Mini                     │"
echo "│  2) Check Mini status               │"
echo "│  3) View API health (:7001)         │"
echo "│  4) List jobs                       │"
echo "│  5) View recent logs                │"
echo "│  6) Fetch artifacts (safe)          │"
echo "│  q) Quit                            │"
echo "└─────────────────────────────────────┘"

read "choice?Select: "
case $choice in
  1) ssh macmini ;;
  2) ssh macmini "hostname && uptime && df -h ~ | tail -1" ;;
  3) curl -s http://100.77.94.44:7001/api/health | jq ;;
  4) curl -s http://100.77.94.44:7001/api/jobs | jq ;;
  5) ssh macmini "tail -50 ~/0luka/server.log" ;;
  6) rsync -av macmini:~/0luka/runtime/opal_artifacts/ ~/0luka-artifacts/ ;;
  q) exit 0 ;;
  *) echo "Invalid option" ;;
esac
```

Then:
```bash
mkdir -p ~/.local/bin
chmod +x ~/.local/bin/setup
# Ensure ~/.local/bin is in PATH
```

---

## Verification Steps

1. **Contract sync:**
   ```bash
   # From Mini
   curl -s http://localhost:7001/api/jobs | jq 'keys'
   # Should return job IDs
   ```

2. **Setup menu:**
   ```bash
   # From MBP
   setup
   # Should show menu, option 3 should show API health
   ```

3. **Antigravity workflow:**
   - Open Antigravity on MBP or Mini
   - Submit job → should appear in `GET /api/jobs`
   - Use `setup` menu to monitor

---

## Architecture Reminder

```
┌──────────────────┐         ┌──────────────────┐
│      MBP         │         │    Mac Mini      │
│  (Antigravity)   │  SSH    │  (Executor)      │
│                  │ ──────► │                  │
│  setup menu      │  API    │  OPAL Server     │
│  (control panel) │ ──────► │  :7001           │
└──────────────────┘         └──────────────────┘
                   Tailscale: 100.77.94.44
```

**Key:** Work from ANY machine, execute on Mini, no rsync of repo needed.

---

## Files to Modify

1. `/Users/icmini/0luka/core/contracts/v1/opal_api.openapi.json` - Add GET /api/jobs
2. Create on **MBP**: `~/.local/bin/setup`

## Already Done (No Action Needed)

- SSH config (MBP has `macmini` alias)
- SSH key auth (passwordless)
- Mini power settings (auto-restart)
- Core repo structure
- OPAL API server implementation
