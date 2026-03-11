# 0luka Secrets Policy

## Purpose

This document defines the canonical secrets discipline for 0luka.

Secrets governance belongs to 0luka core governance, not to any bounded product
module, app shell, or always-open tool session. Antigravity is one consumer of
this policy, not the owner of it.

## Ownership

- `core/governance/` owns the rules for secrets handling.
- `runtime/` owns how secrets are injected into supervised processes.
- `modules/antigravity/` may consume secrets but must not redefine policy.

## Kernel Rules

1. `dotenvx` is the approved environment injection boundary for local and
   supervised runtime startup when encrypted env material is required.
2. `.env` and `.env.local` may exist only as local operator/runtime files and
   must never become the system source of truth.
3. `.env.keys` is local-only and must never be committed.
4. No secret value may be committed into repository source, tests, docs, logs,
   screenshots, or generated artifacts.
5. If a migration cannot preserve secret handling safely, fail closed and stop
   the migration instead of weakening discipline.

## Antigravity-Specific Application

Antigravity runtime entrypoints currently rely on `dotenvx` in bounded startup
flows such as `repos/option/tools/deploy_prod.sh`. That usage is allowed, but
the rule is now owned here under 0luka core governance.

Antigravity must not introduce module-local exceptions for:

- plaintext secret sprawl
- committed env files
- app-local secret governance
- ad-hoc PM2 secret injection outside kernel-approved runtime patterns

## Runtime Injection Standard

- supervised processes may receive secrets at startup time only
- startup wrappers must not log secret material
- runtime crash logs and observability outputs must redact or avoid secrets
- deploy scripts must reference secret injection tools, not embed secret values

## Repository Safety Rules

- do not commit `.env`
- do not commit `.env.local`
- do not commit `.env.keys`
- do not commit secret snapshots or shell history containing secret values
- do not broaden env variable sprawl unless required for a bounded migration

## Migration Rule

During Antigravity kernelization, any secret-bearing deploy/runtime convention
must be re-homed under 0luka governance/runtime ownership before new feature
work resumes.
