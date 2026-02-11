#!/usr/bin/env python3
"""
Seal module - HMAC-SHA256 signing for envelopes and Merkle chain for ledger entries.

Key is auto-generated at ~/.0luka_seal_key if not present.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
from typing import Any, Dict, Optional

KEY_PATH = Path.home() / ".0luka_seal_key"
KEY_LENGTH = 32

# Fix 4: Module-level key cache to avoid re-reading from disk on every call
_CACHED_KEY: bytes | None = None


def _ensure_key() -> bytes:
    """Read or create HMAC key file. Returns raw bytes."""
    if KEY_PATH.exists():
        hex_str = KEY_PATH.read_text(encoding="utf-8").strip()
        if len(hex_str) >= KEY_LENGTH * 2:
            return bytes.fromhex(hex_str[:KEY_LENGTH * 2])
        raise RuntimeError(f"seal_key_corrupted:length={len(hex_str)}")
    key = secrets.token_bytes(KEY_LENGTH)
    tmp = KEY_PATH.with_suffix(".tmp")
    tmp.write_text(key.hex(), encoding="utf-8")
    tmp.chmod(0o600)
    try:
        tmp.rename(KEY_PATH)
    except OSError:
        tmp.unlink(missing_ok=True)
        return _ensure_key()
    return key


def _get_key() -> bytes:
    """Cached key accessor - reads from disk once, then returns from memory."""
    global _CACHED_KEY
    if _CACHED_KEY is None:
        _CACHED_KEY = _ensure_key()
    return _CACHED_KEY


def _canonical_json(data: Any) -> str:
    """Deterministic JSON for signing."""
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def compute_hmac(data: Any, key: Optional[bytes] = None) -> str:
    """Compute HMAC-SHA256 over canonical JSON representation."""
    if key is None:
        key = _get_key()
    canonical = _canonical_json(data)
    return hmac.new(key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_envelope(envelope: Dict[str, Any]) -> Dict[str, Any]:
    """Add HMAC seal to an envelope dict. Returns a new dict with 'seal' field."""
    result = dict(envelope)
    result.pop("seal", None)
    sig = compute_hmac(result)
    result["seal"] = {
        "alg": "hmac-sha256",
        "sig": sig,
    }
    return result


def verify_envelope(envelope: Dict[str, Any]) -> bool:
    """Verify the HMAC seal on an envelope. Returns True if valid."""
    seal = envelope.get("seal")
    if not isinstance(seal, dict):
        return False
    expected_sig = seal.get("sig", "")
    check = dict(envelope)
    check.pop("seal", None)
    actual_sig = compute_hmac(check)
    return hmac.compare_digest(expected_sig, actual_sig)


def chain_ledger_entry(entry: Dict[str, Any], prev_hash: str = "") -> Dict[str, Any]:
    """Add Merkle chain fields to a ledger entry.

    Computes entry_hash = SHA256(prev_hash + canonical_json(entry)).
    """
    result = dict(entry)
    result["prev_hash"] = prev_hash
    canonical = prev_hash + _canonical_json(entry)
    result["entry_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return result


def verify_chain(entries: list) -> bool:
    """Verify the Merkle chain integrity of ledger entries."""
    prev = ""
    for entry in entries:
        expected_prev = entry.get("prev_hash", "")
        if expected_prev != prev:
            return False
        base = {k: v for k, v in entry.items() if k not in ("prev_hash", "entry_hash")}
        canonical = prev + _canonical_json(base)
        expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if entry.get("entry_hash") != expected_hash:
            return False
        prev = entry["entry_hash"]
    return True
