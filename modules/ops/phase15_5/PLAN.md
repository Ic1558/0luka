# WO-15.5.1 PLAN

## Intent
Implement an observability-only heartbeat dropper for Cole without modifying gate, schema, dispatcher, security, or seal behavior.

## Scope Lock
- `tools/ops/heartbeat_dropper.py`
- `core/verify/test_heartbeat_dropper.py`
- `modules/ops/phase15_5/PLAN.md`
- `modules/ops/phase15_5/VERIFY.md`

## Non-goals
- No gate allowlist edits
- No dispatcher logic edits
- No clec schema edits
- No security policy relaxation
