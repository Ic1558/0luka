# Antigravity Issuer Tuple Validation Report (2026-03-13)

## Purpose

Reduce the remaining broker-auth blocker to the narrowest supported root-cause
class.

## Canonical tuple under review

- `SETTRADE_APP_ID`
- `SETTRADE_APP_SECRET`
- `SETTRADE_APP_CODE`
- `SETTRADE_BROKER_ID`

## Current environment context

- environment selector: prod
- runtime mutation: not authorized
- runtime architecture: separate lane, already closed

## Evidence carried in

- auth probe failed
- market probe did not proceed after auth failure
- env injection works
- source-of-value map completed
- shell shadowing absent
- target keys sourced from .env

## Validation classes

- Issuer tuple mismatch
- Broker/app/app_code/account binding mismatch
- Entitlement/scope mismatch
- Revoked or inactive credential set
- Unknown provider-side state

## Best-supported current classification

Best-supported current class:

- Issuer tuple mismatch or issuer-side binding mismatch

Why:

- auth fails at first boundary (401) before market probe can proceed
- local injection and key-source path are already verified
- architecture/runtime lane does not show a failure class explaining auth 401

## What is ruled out

- not architecture failure
- not history loss
- not env injection failure
- not shell shadowing

## Remaining unknowns

- whether tuple is revoked or inactive
- whether entitlement is missing
- whether issuer-side binding differs from local expectation

## Next safe action

- issuer-side tuple confirmation as one atomic set
- record result as MATCH or MISMATCH or UNKNOWN
- keep runtime untouched

## Boundary statement

- this report does not authorize runtime restart
- this report does not authorize credential mutation
- this report does not re-open architecture governance
