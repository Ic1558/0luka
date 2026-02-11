# VERIFY — Baseline Health Tracked

## Commands
```bash
python3 -m pytest core/verify -q
python3 core/health.py --full
```

## Expected
- `pytest core/verify -q` => all tests pass
- `core/health.py --full` => `Status: HEALTHY` and `16/16 passed`
