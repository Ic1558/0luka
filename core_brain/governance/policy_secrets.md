# 0luka Secrets Policy (SOT)

> **Rule 1**: The Single Source of Truth (SOT) for runtime secrets is `/.env.local`.
> **Rule 2**: Agents/Services MUST NOT create `/.env` or `vault/.env` automatically.
> **Rule 3**: If `/.env.local` is missing, the service MUST fail gracefully or report "Configuration Missing", NOT attempt to create it.
> **Rule 4**: `vault/` path is reserved for future use (Non-Goal for now).

## Canonical Paths
- **Active**: `/.env.local` (Root)
- **Legacy/Compat**: `/.env` (Optional, read-only if exists, do not create)
- **Future**: `vault/.env` (Reserved)
