# Antigravity Scan Runtime Service

This directory contains the 0luka runtime-owned wrapper for the Antigravity
production monitoring loop.

Ownership:

- runtime wrapper: `runtime/services/antigravity_scan/runner.zsh`
- delegated implementation: `repos/option/src/antigravity_prod.py`

Phase A.1 keeps the Python domain logic in its current location while moving
runtime startup ownership toward `runtime/services/`.
