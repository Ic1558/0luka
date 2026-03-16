"""AG-68 tests: Operator Workbench."""
import os, sys, json
import pytest
sys.path.insert(0, "/Users/icmini/0luka")


def test_build_workbench_returns_snapshot(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.operator_workbench import build_workbench
    snap = build_workbench(operator_id="test_op")
    assert isinstance(snap, dict)
    assert "workbench_id" in snap
    assert snap["operator_id"] == "test_op"
    assert "panels" in snap


def test_workbench_panels_present(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.operator_workbench import build_workbench
    from runtime.operator_workbench_policy import WORKBENCH_PANELS
    snap = build_workbench()
    for panel in WORKBENCH_PANELS:
        assert panel in snap["panels"], f"Missing panel: {panel}"


def test_workbench_artifacts_written(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.operator_workbench import build_workbench
    build_workbench()
    assert (tmp_path / "state" / "runtime_operator_workbench_latest.json").exists()
    assert (tmp_path / "state" / "runtime_operator_workbench_log.jsonl").exists()
    assert (tmp_path / "state" / "runtime_operator_workbench_index.json").exists()


def test_get_workbench_latest(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.operator_workbench import build_workbench, get_workbench_latest
    snap = build_workbench(operator_id="op_x")
    latest = get_workbench_latest()
    assert latest is not None
    assert latest["workbench_id"] == snap["workbench_id"]


def test_list_workbench_snapshots(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.operator_workbench import build_workbench, list_workbench_snapshots
    build_workbench()
    build_workbench()
    snaps = list_workbench_snapshots()
    assert len(snaps) == 2
