# Manual: OPAL Contract SOT + Executor Consumption

## Purpose

Make `Ic1558/core` the authoritative Source of Truth (SOT) for OPAL OpenAPI and ensure the OPAL server serves that contract from `/openapi.json`.

## SOT Contract Location

- Core repo: `Ic1558/core`
- Contract file: `contracts/v1/opal_api.openapi.json`

## How OPAL Loads The Contract

The OPAL server endpoint `GET /openapi.json` loads bytes from SOT using env-based discovery:

1) `CORE_CONTRACTS_URL` (preferred)
2) `CORE_CONTRACT_URL` (fallback)
3) Default base URL: `https://raw.githubusercontent.com/Ic1558/core/main`

Supported forms:

- URL base directory: `CORE_CONTRACTS_URL=https://raw.githubusercontent.com/Ic1558/core/main`
- URL to file: `CORE_CONTRACTS_URL=https://.../contracts/v1/opal_api.openapi.json`
- Local path (dir): `CORE_CONTRACTS_URL=/path/to/core` (server appends `contracts/v1/...`)
- Local path (file): `CORE_CONTRACTS_URL=/path/to/core/contracts/v1/opal_api.openapi.json`
- file URL: `CORE_CONTRACTS_URL=file:///path/to/core`

## Local Dev Example

```bash
export CORE_CONTRACTS_URL="/Users/you/repos/core"
export OPAL_API_BASE="http://127.0.0.1:7001"
```

## Contract Drift Gate

Run:

```bash
OPAL_API_BASE="$OPAL_API_BASE" python3 tools/validate_opal_contract_runtime.py
```

## Notes

- The server returns contract bytes directly to preserve SOT fidelity (enables byte-identical serving).
