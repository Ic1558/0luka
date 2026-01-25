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
