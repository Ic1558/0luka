#!/usr/bin/env python3
"""Phase 14 tests: analytics-only collector + parsing + outputs."""
from __future__ import annotations

import ast
import importlib.util
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLLECTOR_PATH = ROOT / "tools" / "ops" / "learning_metrics" / "collector.py"
FIXTURE_PATH = ROOT / "core" / "verify" / "fixtures" / "phase14_mock_logs.jsonl"

FORBIDDEN_IMPORTS = {"subprocess", "socket", "requests", "httpx", "urllib", "aiohttp", "core.task_dispatcher"}
FORBIDDEN_CALLS = {"system", "popen", "dispatch_one", "submit_task"}


def _load_collector():
    spec = importlib.util.spec_from_file_location("phase14_collector", COLLECTOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load collector")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod


def _set_root(root: Path) -> dict:
    old = {"ROOT": os.environ.get("ROOT"), "0LUKA_ROOT": os.environ.get("0LUKA_ROOT")}
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    return old


def _restore_env(old: dict) -> None:
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _write_fixture_inputs(root: Path) -> None:
    activity_path = root / "observability" / "activity" / "activity.jsonl"
    ann_path = root / "observability" / "annotations" / "annotations.jsonl"
    activity_path.parent.mkdir(parents=True, exist_ok=True)
    ann_path.parent.mkdir(parents=True, exist_ok=True)

    acts = []
    anns = []
    for line in FIXTURE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        kind = row.pop("kind")
        if kind == "activity":
            acts.append(row)
        else:
            anns.append(row)
    activity_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in acts) + "\n", encoding="utf-8")
    ann_path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in anns) + "\n", encoding="utf-8")


def test_static_safety_scan() -> None:
    tree = ast.parse(COLLECTOR_PATH.read_text(encoding="utf-8"), filename=str(COLLECTOR_PATH))
    src = COLLECTOR_PATH.read_text(encoding="utf-8")

    for bad in FORBIDDEN_IMPORTS:
        assert bad not in src, f"forbidden import token: {bad}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            assert name not in FORBIDDEN_CALLS, f"forbidden call: {name}"

    print("test_static_safety_scan: ok")


def test_metrics_and_recommendations_parsing() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        old = _set_root(root)
        try:
            _write_fixture_inputs(root)
            collector = _load_collector()
            out = collector.collect_metrics()

            assert out["activities"] == 3
            assert out["annotations"] == 3
            assert out["alignment_rate"] == 33.33
            assert out["block_rate"] == 33.33
            assert out["proposals_written"] >= 1

            metrics_file = root / "observability" / "metrics" / "phase14" / "system_kpis.jsonl"
            recs_file = root / "observability" / "recommendations" / "policy_suggestions.jsonl"
            assert metrics_file.exists()
            assert recs_file.exists()

            mrows = [json.loads(x) for x in metrics_file.read_text(encoding="utf-8").splitlines() if x.strip()]
            assert len(mrows) >= 3
            assert all(r.get("schema_version") == "system_metrics.v1" for r in mrows)

            rrows = [json.loads(x) for x in recs_file.read_text(encoding="utf-8").splitlines() if x.strip()]
            assert len(rrows) >= 1
            assert all(r.get("schema_version") == "policy_proposal.v1" for r in rrows)
            print("test_metrics_and_recommendations_parsing: ok")
        finally:
            _restore_env(old)


def main() -> int:
    test_static_safety_scan()
    test_metrics_and_recommendations_parsing()
    print("test_phase14_learning_metrics: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
