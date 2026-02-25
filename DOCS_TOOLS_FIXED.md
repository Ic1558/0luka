# Tools Refactoring & Portability Fix (2026-02-25)

## 🎯 Objective

Resolve tool failures reported by the user and ensure 100% portability (no hardcoded `/Users/icmini` paths).

## 🛠 Fixes Applied

### 1. Legacy Compatibility Wrappers

Created wrappers in `tools/` to bridge the gap between old commands in memory and the new `core_brain` structure:

- `tools/catalog_lookup.zsh` -> Proxies to `core_brain/ops/catalog_lookup.zsh`
- `tools/warroom.zsh` -> Proxies to `tools/ops/decision_box.zsh`
- `tools/ops/verify_lock_manifest.py` -> Proxies to `tools/ops/governance_file_lock.py` (with flags mapping)

### 2. `run_tool.zsh` Update

Added missing verbs used in common workflows:

- `warroom`: Launch decision artifact generator.
- `lock-refresh`: Update governance lock manifest.
- `lock-verify`: Check integrity of critical governance files.

### 3. Hardpath Removal (Portability)

Scanned and removed hardcoded paths in the following files:

- `tools/run_tool.zsh` (Internal paths made relative)
- `tools/save_now.zsh` (Root calculated relative to script)
- `tools/0luka_to_notebook.zsh` (Root calculated relative to script)
- `core_brain/ops/governance/bridge_dispatcher.py` (Calculated root via `Path(__file__)`)

## 🚀 Correct Usage

Standard commands should now work reliably:

```bash
# To generate a decision (Warroom)
zsh tools/run_tool.zsh warroom --title "My Topic" --why "Reason"

# To refresh governance locks
zsh tools/run_tool.zsh lock-refresh

# To search catalog
zsh tools/catalog_lookup.zsh <name>
```

---
*Status: Clean, Portable, Verified.*
