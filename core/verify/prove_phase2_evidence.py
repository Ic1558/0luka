#!/usr/bin/env python3
"""Proof runner for Phase 2 Evidence Enforcement (RunProvenance)."""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _set_env(root: Path) -> dict:
    old = {"ROOT": os.environ.get("ROOT"), "0LUKA_ROOT": os.environ.get("0LUKA_ROOT")}
    os.environ["ROOT"] = str(root)
    os.environ["0LUKA_ROOT"] = str(root)
    return old


def _restore_env(old: dict) -> None:
    for key, val in old.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def _load_modules():
    import core.config as cfg

    importlib.reload(cfg)
    rp = importlib.import_module("core.run_provenance")
    ex = importlib.import_module("core.clec_executor")
    return importlib.reload(rp), importlib.reload(ex)


def run_proof() -> bool:
    root = Path(__file__).resolve().parents[2]
    old = _set_env(root)
    try:
        rp, ex = _load_modules()

        # Required failure event: execution without provenance.
        try:
            ex.execute_clec_ops(
                [{"op_id": "w0", "type": "write_text", "target_path": "artifacts/provenance_fail.txt", "content": "x"}],
                {},
            )
        except ex.CLECExecutorError:
            pass

        # Required success path with provenance.
        ex.execute_clec_ops(
            [{"op_id": "w1", "type": "write_text", "target_path": "artifacts/provenance_ok.txt", "content": "phase2"}],
            {},
            run_provenance={
                "task_id": "phase2_evidence_ok",
                "author": "codex",
                "tool": "CLECExecutor",
                "evidence_refs": ["file:artifacts/provenance_ok.txt", "command:python3 core/verify/prove_phase2_evidence.py"],
            },
        )

        return rp.emit_execution_verified_if_proven(actor="Phase2EvidenceVerifier")
    finally:
        _restore_env(old)


def main() -> int:
    ok = run_proof()
    print("phase2_evidence_proof:", "ok" if ok else "failed")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
