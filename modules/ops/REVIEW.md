# Review Notes — Cole-Run

- Tool is read-only by design.
- Registry caps include allowed read paths and forbidden write/network.
- Delegation in `run_tool` is explicit (`cole-run`) with no passthrough.
- Output is deterministic JSON for automation compatibility.
