#!/usr/bin/env python3
"""Register Paula scheduled mission (hourly) in missions_registry.json. Idempotent."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("LUKA_RUNTIME_ROOT", "/Users/icmini/0luka_runtime")

from runtime.mission_scheduler import load_registry, upsert_mission

upsert_mission({
    "mission_id":      "paula_brief",
    "schedule":        "hourly",
    "handler":         "runtime.paula_controller.run_paula_brief",
    "operator_id":     "boss",
    "provider":        "claude",
    "notify":          False,
    "enabled":         True,
    "last_run_window": None,
})

reg = load_registry()
m = next((x for x in reg if x["mission_id"] == "paula_brief"), None)
print(json.dumps(m, indent=2))
print("OK: paula_brief registered")
