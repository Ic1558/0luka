# Antigravity Runtime Recovery Runbook

## Purpose

This runbook defines a deterministic, evidence-first recovery sequence for
Antigravity runtime incidents.

## Recovery Preconditions

- Treat this runbook as governance guidance, not runtime mutation authority.
- Preserve evidence before any restart or reinstall decision.
- Keep broker auth classification separate from runtime/history classification.

## Canonical Recovery Order

1. verify history artifact existence
2. verify current supervisor owner
3. verify working directory
4. verify entrypoint path exists on disk
5. verify API/port health
6. classify broker auth separately
7. only then consider restart/reinstall

## Evidence Checks

- Verify decision history artifact presence:
  `modules/antigravity/realtime/artifacts/hq_decision_history.jsonl`
- Verify replay/report artifacts where available.
- Record command outputs used for classification.

## Supervisor Verification

Confirm which supervisor currently owns runtime lifecycle and ensure there is no
dual-owner ambiguity.

## Entrypoint Verification

Confirm configured command resolves to maintained on-disk source files. Any
missing referenced entrypoint is drift and blocks restart approval.

## API Verification

Example checks:

- `lsof -i :8089`
- `curl localhost:8089/api/status`
- `curl localhost:8089/api/contract`

These checks validate health signal only. They do not validate broker auth
pairing.

## History Verification

Confirm history continuity from canonical evidence artifact:

- `modules/antigravity/realtime/artifacts/hq_decision_history.jsonl`

If this artifact exists and is internally consistent with logs/reports, history
loss classification is rejected.

## Auth Boundary Check

Classify broker auth independently. Auth failures (for example status class
401) are broker/auth-domain signals and must not be used as proof of runtime
history loss.

## Restart Decision Rule

Restart eligibility may be reconsidered only after:

1. history integrity is proven
2. supervisor ownership is unambiguous
3. entrypoint validity is proven on disk
4. runtime API/port health checks are classified
5. broker auth classification is explicitly separated

## Reinstall Rule

Reinstall is a last-step action. It must not be used as first response to
architecture drift or auth mismatch. Preserve and verify evidence first.

## Stop Conditions

Stop and escalate when:

- evidence is contradictory or incomplete
- supervisor ownership cannot be determined
- entrypoint file existence cannot be proven
- history artifact integrity cannot be established
- broker auth and runtime history are being conflated in the same claim
