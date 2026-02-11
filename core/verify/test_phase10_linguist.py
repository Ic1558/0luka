#!/usr/bin/env python3
"""Phase 10 Linguist tests (offline)."""
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


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _load_synth():
    import core.config as cfg
    import core.run_provenance as prov_mod
    import core.tool_selection_policy as policy_mod
    import core.submit as submit_mod
    import core.task_dispatcher as dispatcher_mod

    importlib.reload(cfg)
    importlib.reload(prov_mod)
    importlib.reload(policy_mod)
    importlib.reload(submit_mod)
    importlib.reload(dispatcher_mod)
    synth = importlib.import_module("modules.nlp_control_plane.core.synthesizer")
    return importlib.reload(synth)


def test_ambiguous_intent_requires_human_clarification() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            synth = _load_synth()
            out = synth.process_nlp_request("do it asap", author="gmx", auto_dispatch=False)
            assert out["status"] == "blocked"
            assert out["reason"] == "human clarification required"

            events = _read_jsonl(root / "observability" / "events.jsonl")
            types = [e.get("type") for e in events]
            assert "policy.linguist.analyzed" in types
            assert "human.clarify.requested" in types
            print("test_ambiguous_intent_requires_human_clarification: ok")
        finally:
            _restore_env(old)


def test_clear_intent_does_not_trigger_clarification() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td).resolve()
        old = _set_env(root)
        try:
            synth = _load_synth()
            out = synth.process_nlp_request("check git status in repo", author="gmx", auto_dispatch=False)
            assert out["status"] in {"submitted", "blocked"}

            events = _read_jsonl(root / "observability" / "events.jsonl")
            clarify = [e for e in events if e.get("type") == "human.clarify.requested"]
            assert len(clarify) == 0
            assert any(e.get("type") == "policy.linguist.analyzed" for e in events)
            print("test_clear_intent_does_not_trigger_clarification: ok")
        finally:
            _restore_env(old)


def main() -> int:
    test_ambiguous_intent_requires_human_clarification()
    test_clear_intent_does_not_trigger_clarification()
    print("test_phase10_linguist: all ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
