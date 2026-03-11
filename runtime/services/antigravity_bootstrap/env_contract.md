# Antigravity Environment Contract

This file documents the variable names consumed by the Antigravity runtime
under 0luka-owned bootstrap governance.

This file is documentation-only and must never contain secret values.

Authority:

- secret handling law: `core/governance/secrets_policy.md`
- bootstrap owner: `runtime/services/antigravity_bootstrap/`

## Required Variables

Required for authenticated Antigravity runtime startup:

- `SETTRADE_APP_ID`
- `SETTRADE_APP_SECRET`

## Required In Some Runtime Modes

Required when broker/app-code aware authenticated flows are used:

- `SETTRADE_BROKER_ID`
- `SETTRADE_APP_CODE`

Required when Telegram alert delivery is expected:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Optional Runtime Variables

- `SETTRADE_PRODUCT`
- `SETTRADE_EXPIRY`
- `SETTRADE_STRIKES`
- `MIN_PROFIT`
- `COMMISSION`
- `WS_URL`
- `SETTRADE_MODE`
- `FIRECRAWL_API_KEY`

## Consumption Mapping

- `runtime/services/antigravity_scan/runner.zsh`
  - delegates to `repos/option/src/antigravity_prod.py`
- `runtime/services/antigravity_realtime/runner.zsh`
  - delegates to `repos/option/src/live.js`
- `repos/option/src/antigravity_master.py`
  - consumes Settrade and Firecrawl runtime variables through delegated startup

## Rules

- names only, never values
- no duplicate secret authority outside 0luka governance/runtime
- new production variables require governance review before adoption
