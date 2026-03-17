# Paula Mission Pack — Read-Only Trading Brief (repos/option)

**Phase:** AG-P11
**Status:** Active
**Role:** Governed read-only trading controller over `repos/option`
**Constraint:** NO live order execution. NO writes to repos/option.

---

## Mission

Paula ingests historical decision records and backtest data from `repos/option` and produces a concise, governed trading brief for operator review. Paula does not execute trades, does not mutate any strategy files, and does not have access to broker APIs.

---

## Source of Truth Files (read-only)

| File | Purpose |
|------|---------|
| `repos/option/artifacts/hq_decision_history.jsonl` | 11 decision records: symbol, direction, global_score, TP/SL, recommendation |
| `repos/option/artifacts/watchdog.log` | Service health: restart events + last healthy timestamp |
| `repos/option/artifacts/lab/backtests/BATCH_V1_3_20260311_234841/comparison_summary.json` | 6 backtest variants: window/horizon, win_rate, expectancy, Sharpe, false-BEAR counts |

---

## Output Categories

| Category | Content |
|----------|---------|
| `repo_health` | Watchdog status (healthy/restarting), last timestamp |
| `strategy_mode` | Last actionable_bias + recommendation from decision log |
| `current_risk_posture` | global_score, TP/SL levels, best backtest variant, false-BEAR count |
| `next_action_recommendation` | Parsed from most recent decision record |
| `open_unknowns` | Missing data, stale timestamps, parse errors |

---

## Invocation

```python
import sys, os
sys.path.insert(0, '/Users/icmini/0luka')
os.environ['LUKA_RUNTIME_ROOT'] = '/Users/icmini/0luka_runtime'

from runtime.paula_controller import run_paula_brief
result = run_paula_brief(operator_id='boss', provider='claude')

import json
print(json.dumps(result, indent=2)[:1000])
```

Or via dotenvx:

```bash
dotenvx run --env-file ~/.env -- python3 -c "
import sys, os
sys.path.insert(0, '/Users/icmini/0luka')
os.environ['LUKA_RUNTIME_ROOT'] = '/Users/icmini/0luka_runtime'
from runtime.paula_controller import run_paula_brief
import json
result = run_paula_brief(operator_id='boss')
print(json.dumps(result, indent=2)[:1000])
"
```

---

## Evidence

Every run writes:
- `$LUKA_RUNTIME_ROOT/state/paula_brief_latest.json` — atomic pointer to latest brief
- `$LUKA_RUNTIME_ROOT/state/paula_brief_log.jsonl` — append log of all briefs
- `$LUKA_RUNTIME_ROOT/artifacts/paula/<brief_id>.json` — durable artifact per brief

---

## Governance

- Approval gate: `task_execution` lane via `runtime.operator_task._check_approval()`
- Inference: `runtime.governed_inference.route_inference()` (governed fabric)
- Path safety: all reads validated under `OPTION_REPO` before access
- No writes to `repos/option` under any condition

---

## Out-of-Scope (Paula must NOT touch)

- `repos/option/src/antigravity_master.py` — raises SystemExit("not restored")
- `repos/option/src/antigravity_prod.py` — stub, do not execute
- `runtime/antigravity/` — live execution engine
- Any broker API or pm2 process
- `repos/option/tools/deploy_prod.sh` — deploy script, reference only

---

## Proof Cases

```python
# V-P11A: Repo audit proof
from runtime.paula_controller import read_option_state
raw = read_option_state()
assert raw["source_files"]
assert raw["decisions"]
print("source_files:", raw["source_files"])
print("last_decision:", raw["decisions"][-1])

# V-P11B: Read-only guarantee
assert all(f.startswith("repos/option") for f in raw["source_files"])

# V-P11D: Evidence integrity
import json
r = json.load(open('/Users/icmini/0luka_runtime/state/paula_brief_latest.json'))
assert r['governed'] == True
assert r['task_id']
assert r['source_files']
assert r['ts']
```
