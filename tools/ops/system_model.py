from __future__ import annotations

import json
import os
from datetime import datetime, UTC
from pathlib import Path
from typing import Any


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not raw:
        raise RuntimeError("LUKA_RUNTIME_ROOT is required")
    return Path(raw).expanduser().resolve()


def build_system_model() -> dict[str, Any]:
    return {
        "schema_version": "system_model.v1",
        "ts_utc": datetime.now(UTC).isoformat(),
        "current_phase": "I",
        "system_classification": "bounded Observability + Reasoning system with decision memory",
        "eligibility_to_act": False,
        "eligibility_reason": "control-plane not implemented",
        "repos_qs_boundary": "frozen_canonical",
        "control_plane_enabled": False,
        "autonomy_enabled": False,
        "decision_memory_present": True,
    }


def write_system_model(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_system_model()
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def main() -> int:
    runtime_root = _runtime_root()
    write_system_model(runtime_root / "state" / "system_model.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
