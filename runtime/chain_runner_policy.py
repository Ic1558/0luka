"""AG-58: Chain Runner Policy — defines chains and step factories."""
from __future__ import annotations

import os
import sys
from pathlib import Path



def _state_dir():
    return os.path.join(os.environ.get("LUKA_RUNTIME_ROOT", str(Path.home() / "0luka_runtime")), "state")


def _step_effectiveness():
    def run():
        try:
            from core.policy.effectiveness_store import run_and_persist
            result = run_and_persist("test_policy")
            return {"status": "PASS", "summary": f"verdict={result.get('verdict', 'unknown')}", "artifacts": ["policy_effectiveness.json"]}
        except Exception as e:
            return {"status": "FAIL", "summary": str(e), "artifacts": []}
    return run


def _step_list_effectiveness():
    def run():
        try:
            from core.policy.effectiveness_store import list_effectiveness
            items = list_effectiveness()
            return {"status": "PASS", "summary": f"count={len(items)}", "artifacts": []}
        except Exception as e:
            return {"status": "FAIL", "summary": str(e), "artifacts": []}
    return run


def _step_create_governance():
    def run():
        try:
            from core.policy.outcome_store import create_governance_record, append_governance_record, write_latest
            rec = create_governance_record({"verdict": "KEEP", "policy_id": "test_policy"})
            append_governance_record(rec)
            write_latest(rec)
            return {"status": "PASS", "summary": f"governance_id={rec.get('governance_id', '?')}", "artifacts": ["policy_outcome_governance.jsonl"]}
        except Exception as e:
            return {"status": "FAIL", "summary": str(e), "artifacts": []}
    return run


def _step_update_patterns():
    def run():
        try:
            from learning.pattern_extractor import update_pattern_registry
            patterns = update_pattern_registry()
            return {"status": "PASS", "summary": f"patterns={len(patterns)}", "artifacts": ["pattern_registry.json"]}
        except Exception as e:
            return {"status": "FAIL", "summary": str(e), "artifacts": []}
    return run


def _step_generate_candidates():
    def run():
        try:
            from learning.policy_candidates import generate_policy_candidates
            cands = generate_policy_candidates()
            return {"status": "PASS", "summary": f"candidates={len(cands)}", "artifacts": ["policy_candidates.jsonl"]}
        except Exception as e:
            return {"status": "FAIL", "summary": str(e), "artifacts": []}
    return run


def _step_learning_metrics():
    def run():
        try:
            from learning.learning_metrics import get_learning_metrics
            m = get_learning_metrics()
            return {"status": "PASS", "summary": f"patterns={m.get('patterns_detected', 0)},candidates={m.get('policy_candidates_generated', 0)}", "artifacts": ["learning_metrics.json"]}
        except Exception as e:
            return {"status": "FAIL", "summary": str(e), "artifacts": []}
    return run


CHAIN_REGISTRY = {
    "policy_review_chain": [
        ("effectiveness_run", _step_effectiveness),
        ("list_effectiveness", _step_list_effectiveness),
    ],
    "governance_review_chain": [
        ("create_governance_record", _step_create_governance),
    ],
    "anomaly_learning_chain": [
        ("update_patterns", _step_update_patterns),
        ("generate_candidates", _step_generate_candidates),
        ("learning_metrics", _step_learning_metrics),
    ],
}
