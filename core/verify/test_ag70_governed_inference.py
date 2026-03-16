"""AG-70 tests: Governed Inference Fabric."""
import os, sys, json
import pytest
sys.path.insert(0, "/Users/icmini/0luka")


def test_route_inference_returns_record(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.governed_inference import route_inference
    rec = route_inference("test prompt", operator_id="op1")
    assert isinstance(rec, dict)
    assert "request_id" in rec
    assert rec["governed"] is True


def test_route_inference_default_provider(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.governed_inference import route_inference
    from runtime.governed_inference_policy import DEFAULT_PROVIDER
    rec = route_inference("hello")
    assert rec["provider"] == DEFAULT_PROVIDER


def test_route_inference_artifacts(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.governed_inference import route_inference
    route_inference("prompt a")
    assert (tmp_path / "state" / "runtime_governed_inference_latest.json").exists()
    assert (tmp_path / "state" / "runtime_governed_inference_log.jsonl").exists()
    assert (tmp_path / "state" / "runtime_governed_inference_index.json").exists()


def test_route_inference_preferred_provider(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.governed_inference import route_inference
    rec = route_inference("hello", preferred_provider="claude")
    assert rec["provider"] == "claude"


def test_list_inference_requests(tmp_path):
    os.environ["LUKA_RUNTIME_ROOT"] = str(tmp_path)
    from runtime.governed_inference import route_inference, list_inference_requests
    route_inference("p1")
    route_inference("p2")
    reqs = list_inference_requests()
    assert len(reqs) == 2
