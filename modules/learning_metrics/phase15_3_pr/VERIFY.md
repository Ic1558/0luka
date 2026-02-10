# VERIFY — Phase 15.3 Pattern-Killer

## Commands
1. `python3 core/verify/test_phase15_3_pattern_killer.py`
   - Result: `test_phase15_3_pattern_killer: all ok`
2. `python3 -m pytest core/verify -q`
   - Result: `113 passed`
3. `python3 core/health.py --full`
   - Result: `Status: HEALTHY` and `Tests: 16/16 passed`

## Determinism Checks Covered
- Stable detect ordering
- Empty replacement rewrite behavior
- Stable scoring for same input
- JSONL schema/format rejection for invalid lines
- End-to-end detect -> rewrite -> score
