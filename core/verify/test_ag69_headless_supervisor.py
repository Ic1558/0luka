"""AG-69 tests: Headless Runtime Supervisor."""
import os, sys, json
import pytest
sys.path.insert(0, "/Users/icmini/0luka")


def test_supervisor_check_runs(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.headless_supervisor import run_supervisor_check
    report = run_supervisor_check(operator_id="test_op")
    assert isinstance(report, dict)
    assert "check_id" in report
    assert "overall_status" in report
    assert "services" in report


def test_supervisor_services_listed(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.headless_supervisor import run_supervisor_check
    from runtime.headless_supervisor_policy import WATCHED_SERVICES
    report = run_supervisor_check()
    service_names = [s["service"] for s in report["services"]]
    for svc in WATCHED_SERVICES:
        assert svc in service_names


def test_supervisor_artifacts_written(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.headless_supervisor import run_supervisor_check
    run_supervisor_check()
    assert (tmp_path / "state" / "runtime_headless_supervisor_latest.json").exists()
    assert (tmp_path / "state" / "runtime_headless_supervisor_log.jsonl").exists()
    assert (tmp_path / "state" / "runtime_headless_supervisor_index.json").exists()


def test_supervisor_degraded_when_absent(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.headless_supervisor import run_supervisor_check
    report = run_supervisor_check()
    # No state files exist yet → all services ABSENT → DEGRADED
    assert report["overall_status"] == "DEGRADED"
    for svc in report["services"]:
        assert svc["status"] in ("ABSENT", "ALIVE", "UNKNOWN", "ERROR")


def test_supervisor_alive_when_state_exists(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    sd = tmp_path / "state"
    sd.mkdir()
    # Seed chain_runner state file
    (sd / "runtime_chain_runner_latest.json").write_text(
        json.dumps({"ts_evaluated": "2026-03-16T00:00:00+00:00"})
    )
    from runtime.headless_supervisor import run_supervisor_check
    report = run_supervisor_check()
    chain_status = next(s for s in report["services"] if s["service"] == "chain_runner")
    assert chain_status["status"] == "ALIVE"
