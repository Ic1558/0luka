# OpenCode TODO: Final Tasks

**Updated:** 2026-02-05

## Status Summary

| Item | Status |
|------|--------|
| SSH MBP → Mini | ✅ Done |
| Reboot test | ✅ Passed |
| ic1558/core repo | ✅ Exists |
| OpenAPI contract | ✅ v1.3.0 |
| OPAL API server | ✅ Running |

---

## Remaining Tasks (2 Items)

### Task 1: Sync Contract with Implementation ⚠️

**Problem:** `GET /api/jobs` is implemented but NOT in contract.

**File:** `/Users/icmini/0luka/core/contracts/v1/opal_api.openapi.json`

**Add to paths section:**
```json
"/api/jobs": {
  "get": {
    "operationId": "listJobs",
    "summary": "List all jobs",
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

Then commit:
- `runtime/apps/opal_api/opal_api_server.py`
- `core/contracts/v1/opal_api.openapi.json`

---

### Task 2: Create Setup Menu on MBP ❌

**File:** `~/.local/bin/setup` (on MBP, not Mini)

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
```

---

## Verification

```bash
# Test contract sync
curl -s http://100.77.94.44:7001/api/jobs | jq 'keys'

# Test setup menu (on MBP)
setup
```

---

## Full Plans (Reference)

- `antigravity_seamless_final.md` - Latest plan
- `core_architecture_phased.md` - Full architecture
