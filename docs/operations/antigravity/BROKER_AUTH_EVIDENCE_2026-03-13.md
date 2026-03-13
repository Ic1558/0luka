# Antigravity Broker Auth Evidence (2026-03-13)

## Purpose

Record the evidence currently available for the broker auth blocker.

## Current status

- auth status: 401
- pairing result: MISMATCH
- runtime execution approval: NOT APPROVED
- restart status: not authorized through runtime lane

## Evidence already known

- source-of-value map completed
- shell shadowing: none
- target SETTRADE_* keys sourced from .env
- dotenvx/runtime injection works
- environment selector: prod
- isolated auth probe failed
- isolated market probe failed because auth failed first

## Evidence interpretation

- this is not an architecture failure
- this is not history loss
- this is not an env injection failure
- most likely remaining class is issuer tuple validity or binding, or
  entitlement mismatch

## Remaining unknowns

- issuer tuple validation outcome
- entitlement or scope validation outcome
- whether current tuple is revoked or inactive
- whether broker/app/app_code/account binding matches issuer record

## Boundary statement

- no runtime mutation authorized
- no restart authorized through this evidence document
- broker auth remains separate from runtime architecture remediation

## Next safe action

- perform or record a fresh isolated auth probe
- perform or record a fresh isolated market probe
- validate issuer tuple as one atomic set
- reduce result to MATCH or MISMATCH or UNKNOWN
