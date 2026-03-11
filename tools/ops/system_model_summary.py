from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def _runtime_root() -> Path:
    raw = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not raw:
        raise RuntimeError("LUKA_RUNTIME_ROOT is required")
    return Path(raw).expanduser().resolve()


def _count_list_field(model: dict[str, Any], key: str) -> int:
    value = model.get(key)
    return len(value) if isinstance(value, list) else 0


def derive_summary(model: dict[str, Any]) -> dict[str, Any]:
    return {
        "ts_utc": model.get("ts_utc"),
        "kernel_components": _count_list_field(model, "kernel_components"),
        "observability_surfaces": _count_list_field(model, "observability_surfaces"),
        "decision_layer_present": bool(model.get("decision_memory_present")),
        "autonomy_layer_present": bool(model.get("autonomy_enabled")),
    }


def generate_summary(runtime_root: Path) -> None:
    model_path = runtime_root / "state" / "system_model.json"
    model = json.loads(model_path.read_text(encoding="utf-8"))
    if not isinstance(model, dict):
        raise RuntimeError("system_model.json must contain an object")

    summary_path = runtime_root / "state" / "system_model_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = summary_path.with_suffix(summary_path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(derive_summary(model), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(summary_path)


def main() -> int:
    generate_summary(_runtime_root())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
