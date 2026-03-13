# Antigravity Architecture Contract

- Version: 1.0
- Effective Date: 2026-03-13
- Status: Ratified
- Owner: 0luka Architecture Authority
- Change Control: Architecture Review (ADR Process)

## Related References

- `docs/architecture/0LUKA_ARCHITECTURE_CONTRACT.md`
- `docs/architecture/0LUKA_LAYER_CONTRACT.md`
- `docs/architecture/adr/ADR-001-capability-ownership-and-layer-model.md`
- `docs/architecture/adr/ADR-UNRESOLVED-INDEX.md`

## Intent

This contract defines the canonical architecture boundaries for Antigravity in
0luka. It exists to prevent supervision, entrypoint, path, environment, and
interpretation drift.

## Core Law

Antigravity historical data must remain recoverable even when UI or runtime
access is degraded.

Therefore:

1. Session and decision history are filesystem artifacts first.
2. UI surfaces are consumers of history, not owners of history.
3. Supervisor state does not redefine architecture ownership.
4. Broker auth failure is not evidence of runtime history loss.

## Canonical Runtime Ownership

1. The canonical workspace root for this runtime domain is
   `/Users/icmini/0luka/repos/option`.
2. The canonical Antigravity runtime application area is
   `repos/option/modules/antigravity/realtime/`.
3. The canonical decision history artifact is
   `repos/option/modules/antigravity/realtime/artifacts/hq_decision_history.jsonl`.
4. Human-readable replay and investigation reports under
   `g/reports/antigravity/` are derivative evidence, not primary runtime state.

## Runtime Supervision Contract

1. Two historical supervision eras are recognized:
   - Era A: launchd (`com.antigravity.controltower`) in the 2026-03-12 session.
   - Era B: PM2 in later Track B and Track C runtime investigations.
2. Exactly one supervisor may be treated as current live owner at a time.
3. Supervisor authority includes process lifecycle management only.
4. Supervisor authority does not include redefining architecture ownership,
   history storage truth, or canonical entrypoint law.

## Entrypoint Contract

1. Canonical runtime entrypoint chains must resolve to maintained on-disk files.
2. The following state is non-canonical:
   - live command references a missing path
   - legacy path is treated as maintained current source
   - stale process state is promoted to architecture authority
3. Historical reports may reference legacy paths. Historical mention does not
   grant current ownership.

## Environment Chain Contract

1. Local env chain may include:
   - `.env`
   - `.env.keys`
   - `settradesdkv2_config.txt`
2. Environment load success proves only value injection.
3. Environment load success does not prove issuer tuple validity, broker
   entitlement, or market access validity.

## History and Evidence Contract

1. History continuity is determined by evidence artifacts, with
   `hq_decision_history.jsonl` as primary continuity evidence.
2. UI rendering failure must not be interpreted as data loss without filesystem
   evidence.
3. If UI fails and history artifact exists, classification must default to
   runtime/UI access inconsistency.

## Broker/Auth Boundary Contract

1. Broker authentication is a separate layer from runtime/UI wiring.
2. Broker auth failure must be classified independently from runtime health and
   history integrity.
3. The equivalence `broker auth fail == runtime/history fail` is forbidden.

## Drift Classification Model

Incidents must classify one or more domains:

1. Supervisor Drift
2. Entrypoint Drift
3. Runtime Path Drift
4. Environment Chain Drift
5. Broker Auth Drift
6. UI Visibility Drift
7. Historical Documentation Drift

## Canonical Incident Interpretation Rules

1. Historical session success remains valid unless contradicted by stronger
   evidence from the same time window.
2. Later drift does not erase earlier operational truth.
3. Filesystem evidence outranks UI symptom alone.
4. Supervisor state does not redefine history truth.
5. Auth mismatch does not imply data loss.

## Required Evidence for Runtime Validity

A runtime claim is evidence-backed only with at least one of:

- successful `GET /api/status`
- successful `GET /api/contract`
- confirmed bind on port 8089
- append activity in `hq_decision_history.jsonl`
- syntax validation before restart in the same change window
- supervisor restart/reload evidence

## Required Evidence for History Integrity

History integrity is preserved when:

1. `hq_decision_history.jsonl` exists.
2. Replay exports or equivalent logs exist.
3. Timeline evidence is internally consistent across reports.
4. No evidence shows destructive deletion of canonical history artifacts.

## Canonical Recovery Order

Recovery classification must follow this order:

1. verify history artifact existence
2. verify current supervisor owner
3. verify working directory
4. verify entrypoint path exists on disk
5. verify API/port health
6. classify broker auth separately
7. only then consider restart or reinstall

## Reinstall Rule

Reinstall is not primary recovery for architecture drift. Reinstall may be
considered only after history evidence is preserved and drift classification is
completed.

## Non-Negotiable Guardrails

The following are forbidden:

- dual live supervisor ambiguity
- stale entrypoints treated as canonical
- UI treated as source of truth for history existence
- auth failure treated as evidence of data loss
- undocumented runtime ownership changes

## Canonical Current Interpretation

1. Historical truth: the 2026-03-12 control tower runtime session was
   operational and evidence-backed.
2. Later truth: runtime drift occurred in later supervision/runtime states.
3. Current blocker truth: broker auth pairing mismatch is a separate blocker
   domain from runtime history continuity.

## Change Control

Any change to supervisor owner, working directory, canonical entrypoint,
history artifact location, or environment contract must be reviewed through the
ADR process and cross-referenced in canonical architecture docs.

## Final Law

Antigravity history is owned by evidence artifacts, not by whichever runtime or
UI happens to be active at a given moment.

## Incident Closure Record (2026-03-13)

- Incident classification: Architecture Drift + Credential Pairing Mismatch
- Historical data loss: Not observed
- Track A: Closed
- Track B: Closed
- Track C: Open
