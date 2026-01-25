# Standard Operating Procedure (SOP): Script Promotion & Retention

**Version**: 1.0 (2026-01-26)
**Status**: ACTIVE

## 1. The Rule (Hard Boundary)
**Any script created for a temporary purpose (incident response, one-time migration, dry-run validation) MUST be moved to the Retention Area immediately after use.**

*   **Retention Area**: `~/0luka/observability/antigravity_tmp/scripts/`
*   **Naming Convention**: `YYMMDD_<purpose>.zsh` (e.g., `260126_stop_bleeding.zsh`)
*   **Artifacts**: Store execution evidence in `~/0luka/observability/antigravity_tmp/artifacts/<purpose>/`.

## 2. The Catalog (Promoted Tools)
Scripts are only "promoted" to the official Catalog (`~/0luka/tools/` or `~/0luka/ops/tools/`) if they pass the **6 Gates of Maturity**.

### The 6 Gates
1.  **Repeatability**: Idempotent or guarded. Safe to run multiple times.
2.  **Scope Safety**: Operates strictly within allowed paths (e.g., `LUKA_ROOT`). No absolute path hardcoding outside the repo.
3.  **Interface Quality**: Has `--help`. Accepts parameters/env vars (not hardcoded assumptions).
4.  **Observability**: Writes to standard logs (`~/0luka/logs/`) or emits Beacon events.
5.  **Failure Behavior**: Fails fast (exit non-zero) on error.
6.  **Demand Signal**: Clear use case for recurring execution (e.g., weekly cron, dependency).

### Promotion Tiers
| Tier | Location | Description |
| :--- | :--- | :--- |
| **Tier 1: Retention** | `observability/antigravity_tmp/scripts/` | Default for all new scripts. Forensics & Audit only. |
| **Tier 2: Candidate** | `tools/candidates/` | Cleaned, parameterized, but waiting for full testing or demand. |
| **Tier 3: Catalog** | `tools/` | Fully supported. Documented in `tools/catalog_lookup.zsh` (if applicable). |

## 3. Promotion Workflow
To promote a script from Retention to Catalog:
1.  **Refactor**: Add `--help`, replace hardcoded paths with params/env.
2.  **Verify**: Run with `--dry-run` or in a safe context.
3.  **Move**: Move file to `tools/` or valid subdirectory.
4.  **Register**: Update `tools/CATALOG.md` (or equivalent) with usage.

## 4. Maintenance
*   **Retention Policy**: Tier 1 scripts are subject to 30-day auto-deletion rules.
*   **Catalog Audit**: Tier 3 scripts verify their own integrity (hash checks).

**Owner**: Governance (gmx)
