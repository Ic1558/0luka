#!/usr/bin/env python3
"""Tests for seal module."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.seal import (
    chain_ledger_entry,
    compute_hmac,
    sign_envelope,
    verify_chain,
    verify_envelope,
)


def test_sign_and_verify():
    """sign_envelope adds seal; verify_envelope validates it."""
    envelope = {"v": "0luka.envelope/v1", "type": "task.request", "payload": {"task": {"task_id": "t1"}}}
    signed = sign_envelope(envelope)
    assert "seal" in signed
    assert signed["seal"]["alg"] == "hmac-sha256"
    assert verify_envelope(signed)


def test_tampered_fails_verify():
    """Modifying a signed envelope fails verification."""
    envelope = {"v": "0luka.envelope/v1", "type": "task.request", "payload": {"task": {"task_id": "t1"}}}
    signed = sign_envelope(envelope)
    signed["payload"]["task"]["task_id"] = "tampered"
    assert not verify_envelope(signed)


def test_compute_hmac_deterministic():
    """Same input always produces the same HMAC."""
    data = {"a": 1, "b": [2, 3]}
    h1 = compute_hmac(data)
    h2 = compute_hmac(data)
    assert h1 == h2
    assert len(h1) == 64


def test_chain_ledger_entry():
    """chain_ledger_entry adds prev_hash and entry_hash."""
    entry = {"task_id": "t1", "status": "committed", "ts": "2026-02-10T00:00:00Z"}
    chained = chain_ledger_entry(entry, "")
    assert "prev_hash" in chained
    assert "entry_hash" in chained
    assert chained["prev_hash"] == ""
    assert len(chained["entry_hash"]) == 64


def test_chain_integrity():
    """verify_chain validates a correct chain and rejects a tampered one."""
    entries = []
    prev = ""
    for i in range(3):
        entry = {"task_id": f"t{i}", "status": "committed", "ts": f"2026-02-10T00:0{i}:00Z"}
        chained = chain_ledger_entry(entry, prev)
        entries.append(chained)
        prev = chained["entry_hash"]

    assert verify_chain(entries)

    entries[1]["status"] = "tampered"
    assert not verify_chain(entries)


def test_no_seal_fails_verify():
    """Envelope without seal fails verification."""
    envelope = {"v": "0luka.envelope/v1", "type": "task.request"}
    assert not verify_envelope(envelope)


if __name__ == "__main__":
    test_sign_and_verify()
    test_tampered_fails_verify()
    test_compute_hmac_deterministic()
    test_chain_ledger_entry()
    test_chain_integrity()
    test_no_seal_fails_verify()
    print("test_seal: 6/6 passed")
