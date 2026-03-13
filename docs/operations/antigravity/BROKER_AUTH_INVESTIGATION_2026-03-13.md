# Antigravity Broker Auth Investigation (2026-03-13)

## 1. Investigation Scope

This ops lane is separate from architecture governance. It focuses only on
broker authentication behavior and 401 pairing mismatch analysis.

## 2. Known Symptoms

Current observed failure state:

- 401 response
- pairing mismatch
- broker authentication failure
- restart attempts do not change result

## 3. Boundary Conditions

- runtime mutation is not authorized
- this investigation cannot change architecture
- runtime execution remediation requires separate approval

## 4. Hypothesis List

Possible root causes:

- environment selector mismatch
- issuer tuple mismatch
- broker/app/app_code/account binding mismatch
- entitlement or scope mismatch
- token audience mismatch
- incorrect key source

## 5. Evidence Required

Required evidence set:

- auth probe output
- market probe output
- environment source-of-truth
- issuer tuple validation
- token payload inspection

## 6. Next Safe Actions

Allowed actions without runtime mutation:

- inspect environment configuration
- inspect auth request structure
- compare expected issuer tuple
- collect probe evidence
