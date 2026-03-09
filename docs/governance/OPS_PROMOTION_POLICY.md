# OPS Promotion Policy

Status: Active

Ops / launchd / bootstrap scripts follow:

`QUARANTINE -> VERIFY -> PROMOTE`

## Promotion Requirements (All Required)

1. Owner
- Explicit owner: `platform` / `ops` / `runtime`.

2. Runbook
- Operator-facing usage and recovery instructions in `docs/runbooks/<script>.md`.

3. Safety
- Bounded scope.
- Fail-fast defaults (`set -euo pipefail`).
- Logging suitable for audit/incident review.
- Non-destructive default behavior, or explicit approval requirement for destructive actions.
- Prefer `--dry-run` mode when applicable.

4. Verification
- Test, dry-run proof, or repeatable verification evidence (e.g. `tools/verify/*` or an integration test).

## Rules

- Machine-specific rescue scripts stay quarantined.
- One-off incident scripts stay quarantined.
- Only reusable, reviewed, bounded scripts may be promoted into tracked platform assets.

