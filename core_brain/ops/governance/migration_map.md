# 0luka Root Migration Map

Current violations → Target locations:

## Immediate Actions

1. `g/` → **DELETE** (legacy, no migration)
2. `tools/` → `ops/tools/`
3. `config/` → `core/config/`
4. `logs/` → `observability/logs/`
5. `mcp/` → `runtime/mcp/`
6. `system/` → `runtime/system/`
7. `artifacts/` → `observability/artifacts/`
8. `workspaces/` → `runtime/workspaces/`
9. `catalog/` → `core/catalog/` (if governance) or `ops/catalog/` (if tooling)
10. `prps/` → `core/governance/prps/` (merge with existing)
11. `architecture.md` → `core/architecture.md`
12. `opencode.json` → `runtime/opencode.json`

## Migration Script

```bash
#!/usr/bin/env zsh
# Run from ~/0luka

# Create target structure
mkdir -p ops/tools core/config observability/{logs,artifacts} runtime/{mcp,system,workspaces}

# Move (not copy)
mv tools ops/
mv config core/
mv logs observability/
mv mcp runtime/
mv system runtime/
mv artifacts observability/
mv workspaces runtime/
mv architecture.md core/
mv opencode.json runtime/

# Catalog - needs decision
# mv catalog core/  # or ops/

# Delete legacy
rm -rf g/

# Merge prps if needed
# mv prps/* core/governance/prps/ && rmdir prps
```

## Verification

After migration:
```bash
zsh ops/governance/gates/00_root_allowlist_check
# Should exit 0
```

## Governance Mutation Paths

### Certified path
- `ops/governance/rpc_client.py` -> `ops/governance/gate_runnerd.py` via `runtime/sock/gate_runner.sock`
- Only `rpc_client.py` is authorized to submit mutation commands (`run_task`, `execute_action`, `set_alarm`).

### Legacy paths (disabled)
- `com.02luka.clc-bridge` LaunchAgent (`~/Library/LaunchAgents/com.02luka.clc-bridge.plist`) -> `~/02luka/tools/watchers/clc_bridge.zsh` (disabled + guarded in LaunchAgents/disabled)
- `com.02luka.auto_wo_bridge_v27` LaunchAgent symlink (legacy WO bridge) -> `LocalProjects/02luka_local_g/...` (disabled + guarded in LaunchAgents/disabled)

### Residual noise (monitor)
- `g/tools/clc_wo_bridge_daemon.py` (owner: legacy/02luka, status: no active LaunchAgent/cron found; log-only noise)
- `g/tools/deploy_expense_pages_watch.zsh` (owner: legacy/02luka, status: no active LaunchAgent/cron found; log-only noise)
- `mcp/servers/mcp-memory/package.json` runner (owner: legacy/02luka, status: no active LaunchAgent/cron found; log-only noise)
