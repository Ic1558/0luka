# Antigravity Realtime Runtime Service

This directory contains the 0luka runtime-owned wrapper for the Antigravity
real-time bug-hunter service.

Ownership:

- runtime wrapper: `runtime/services/antigravity_realtime/runner.zsh`
- delegated implementation: `repos/option/src/live.js`

Phase A.1 keeps the Node runtime logic in its current location while moving
runtime startup ownership toward `runtime/services/`.
