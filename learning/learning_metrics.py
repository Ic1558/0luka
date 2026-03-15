"""AG-21: Learning metrics — aggregate counts from learning plane state files.

Storage: $LUKA_RUNTIME_ROOT/state/learning_metrics.json

Updated on each call to get_learning_metrics() — no daemon required.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import os

_METRICS_NAME = "learning_metrics.json"


def _state_dir() -> Path:
    runtime_root = os.environ.get("LUKA_RUNTIME_ROOT", "").strip()
    if not runtime_root:
        raise RuntimeError("LUKA_RUNTIME_ROOT not set")
    d = Path(runtime_root) / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_learning_metrics() -> dict[str, Any]:
    """Compute and persist learning plane metrics.

    Reads:
      - learning_observations.jsonl
      - pattern_registry.json
      - policy_candidates.jsonl

    Returns dict with:
      observation_count, patterns_detected,
      policy_candidates_generated, candidate_pending,
      computed_at
    """
    sd = _state_dir()

    # Observation count
    obs_log = sd / "learning_observations.jsonl"
    observation_count = 0
    if obs_log.exists():
        observation_count = sum(
            1 for ln in obs_log.read_text(encoding="utf-8").splitlines() if ln.strip()
        )

    # Patterns detected
    pattern_reg = sd / "pattern_registry.json"
    patterns_detected = 0
    if pattern_reg.exists():
        try:
            data = json.loads(pattern_reg.read_text(encoding="utf-8"))
            patterns_detected = len(data) if isinstance(data, list) else 0
        except (json.JSONDecodeError, OSError):
            pass

    # Policy candidates
    cand_log = sd / "policy_candidates.jsonl"
    policy_candidates_generated = 0
    candidate_pending = 0
    if cand_log.exists():
        for ln in cand_log.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            try:
                c = json.loads(ln)
                policy_candidates_generated += 1
                if c.get("approval_state") == "PENDING":
                    candidate_pending += 1
            except json.JSONDecodeError:
                pass

    metrics = {
        "observation_count": observation_count,
        "patterns_detected": patterns_detected,
        "policy_candidates_generated": policy_candidates_generated,
        "candidate_pending": candidate_pending,
        "computed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Persist for API serving
    metrics_path = sd / _METRICS_NAME
    tmp = metrics_path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        tmp.replace(metrics_path)
    except OSError:
        pass

    return metrics
