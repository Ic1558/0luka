# Antigravity Provider-Side Confirmation Record (2026-03-13)

## Purpose

Define the exact provider or issuer-side confirmations required to reduce the
remaining broker-auth blocker.

## Canonical tuple under external confirmation

- `SETTRADE_APP_ID`
- `SETTRADE_APP_SECRET`
- `SETTRADE_APP_CODE`
- `SETTRADE_BROKER_ID`

## Questions requiring provider-side truth

- Do these four values belong to the same issuer record?
- Is the credential set active or revoked?
- Is the set valid for prod?
- Is broker binding correct?
- Is account/app/app_code binding correct?
- Is market entitlement or scope present for the attempted endpoints?

## Current local conclusions

- local env injection works
- local key source path is understood
- auth fails before market access
- architecture lane is not the blocker

## What this record does not do

- does not authorize runtime restart
- does not authorize credential mutation
- does not change architecture classification
- does not prove provider truth locally

## Expected response classes

- MATCH
- MISMATCH
- REVOKED_OR_INACTIVE
- ENTITLEMENT_MISSING
- UNKNOWN_PROVIDER_STATE

## Next safe action

- obtain provider-side confirmation for the tuple as one atomic set
- record result using the allowed response classes
- keep runtime untouched
