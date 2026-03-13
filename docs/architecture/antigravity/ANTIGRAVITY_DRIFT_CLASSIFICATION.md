# Antigravity Drift Classification

## Purpose

This document defines the drift taxonomy used for Antigravity incident
classification and governance review.

## Drift Domains

1. Supervisor Drift
   - Host-level runtime supervision ownership changes or overlaps.
2. Entrypoint Drift
   - Runtime commands reference stale, missing, or non-canonical entrypoints.
3. Runtime Path Drift
   - Working directory and path assumptions diverge from documented runtime
     path truth.
4. Environment Chain Drift
   - Environment source chain changes or precedence creates ambiguous runtime
     configuration.
5. Broker Auth Drift
   - Credential tuple, entitlement, or account binding diverges from expected
     broker auth validity.
6. UI Visibility Drift
   - UI fails to render current or historical state while underlying artifacts
     remain present.
7. Historical Documentation Drift
   - Documentation claims conflict with observed runtime/file truth or canonical
     governance contracts.

## Interpretation Rules

1. Classify each incident across one or more drift domains.
2. Do not collapse multiple domains into a single root-cause claim.
3. Use filesystem evidence before UI symptom for history continuity judgment.
4. Broker auth failure must not be interpreted as runtime history loss.

## Classification Priorities

Use this priority when triaging:

1. history integrity evidence
2. supervision ownership and entrypoint validity
3. runtime path and environment chain correctness
4. broker auth status
5. documentation consistency

## Examples

- Supervisor Drift: launchd and PM2 both treated as active runtime owners.
- Entrypoint Drift: live process command references a path missing on disk.
- Runtime Path Drift: command assumes path resolution outside verified working
  directory.
- Environment Chain Drift: runtime loads from unexpected env precedence.
- Broker Auth Drift: auth status class 401 with pairing mismatch.
- UI Visibility Drift: UI cannot load session view while JSONL history exists.
- Historical Documentation Drift: report labels legacy path as maintained source
  after file removal.

## Relationship to Incident Review

This taxonomy is used by:

- `ANTIGRAVITY_ARCHITECTURE_CONTRACT.md` for authoritative interpretation
- `ANTIGRAVITY_RUNTIME_RECOVERY_RUNBOOK.md` for deterministic recovery order
- architecture guard and governance review for consistent drift signaling
