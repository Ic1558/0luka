# DECISION_EMAIL_ORCHESTRATION_20260213

- Date: 2026-02-13
- Status: Accepted
- Scope: Production ingress for Luka.ai@theedges.com with fail-closed execution.

## Decision

Adopt a dedicated email orchestration ingress flow with immutable evidence capture and strict gate ordering:
1. Ingest IMAP unseen mail and persist raw `.eml` evidence.
2. Parse normalized task object and validate gates fail-closed.
3. Route validated tasks to Redis request bus and await deterministic response channel.
4. Reply through SMTP with REJECT/FAILED/DONE status and proof pack paths.

## Rationale

- Enforces ring declaration and token gate before any dispatch.
- Preserves governance rails by explicitly forbidding destructive operations by default.
- Keeps operational proof artifacts deterministic for R2/R3 audit replay.

## Consequences

- Email requests without DKIM pass, token, allowlisted sender/domain, or ring are rejected.
- Timeout on Redis response yields FAILED with exit code and evidence path references.
- Governance lock manifest must include this decision and contract file.
