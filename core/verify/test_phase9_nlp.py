#!/usr/bin/env python3
"""Phase 9 NLP control plane verification tests."""
from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _set_env(root: Path) -> dict:
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


def _load_modules():
    import core.config as cfg

    importlib.reload(cfg)
    import core.submit as submit_mod
    import core.task_dispatcher as dispatcher_mod
    import core.tool_selection_policy as policy_mod
    import core.run_provenance as prov_mod

    importlib.reload(submit_mod)
    importlib.reload(dispatcher_mod)
    importlib.reload(policy_mod)
    importlib.reload(prov_mod)
    synth = importlib.import_module("modules.nlp_control_plane.core.synthesizer")
    return importlib.reload(synth)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def test_canonical_clec_v1_shape() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            synth = _load_modules()
            task = synth.synthesize_to_canonical_task("Check git status in the repo", author="gmx", task_id="task_phase9_001")
            assert set(task.keys()) == {"schema_version", "task_id", "author", "intent", "risk_hint", "ops", "evidence_refs"}
            assert task["schema_version"] == "clec.v1"
            assert task["risk_hint"] == "local"
            assert task["ops"][0]["type"] == "run"
            print("test_canonical_clec_v1_shape: ok")
        finally:
            _restore_env(old)


def test_protected_requires_human_escalate() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            synth = _load_modules()
            out = synth.process_nlp_request(
                "Login to dash.cloudflare.com to check logs",
                author="gmx",
                credentials_present=False,
                session_id="phase9-protected",
                auto_dispatch=False,
            )
            assert out["status"] == "blocked"
            events = _read_jsonl(root / "observability" / "events.jsonl")
            chain = [e.get("type") for e in events]
            assert "policy.sense.started" in chain
            assert "policy.reasoning.select" in chain
            assert "human.escalate" in chain
            print("test_protected_requires_human_escalate: ok")
        finally:
            _restore_env(old)


def test_forbidden_secret_discovery_hard_fails() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            synth = _load_modules()
            try:
                synth.synthesize_to_canonical_task("Find all API keys in the repo", author="gmx")
                raise AssertionError("must hard fail on forbidden secret discovery")
            except synth.NLPControlPlaneError as exc:
                assert "forbidden_secret_discovery" in str(exc)
            print("test_forbidden_secret_discovery_hard_fails: ok")
        finally:
            _restore_env(old)


def test_local_task_through_dispatcher_has_provenance() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            synth = _load_modules()
            out = synth.process_nlp_request(
                "Check git status in the repo",
                author="gmx",
                session_id="phase9-local",
                auto_dispatch=True,
            )
            assert out["status"] in {"committed", "rejected", "skipped"}
            rows = _read_jsonl(root / "observability" / "artifacts" / "run_provenance.jsonl")
            assert any(r.get("tool") == "DispatcherService" for r in rows)
            print("test_local_task_through_dispatcher_has_provenance: ok")
        finally:
            _restore_env(old)


def main() -> int:
    test_canonical_clec_v1_shape()
    test_protected_requires_human_escalate()
    test_forbidden_secret_discovery_hard_fails()
    test_local_task_through_dispatcher_has_provenance()
    print("test_phase9_nlp: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
