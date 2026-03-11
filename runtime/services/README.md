# Runtime Services

This directory is reserved for 0luka-owned service definitions and startup
conventions.

Phase A kernelization rule:

- service persistence belongs to `runtime/`
- bounded product modules may expose entrypoints
- bounded product modules do not own the host survival layer

Phase A.1 runtime ownership rule:

- runtime wrappers under `runtime/services/` are the first-class service
  entrypoints for Antigravity
- delegated implementation may still live under `repos/option/src/`
- deploy/bootstrap paths should point to runtime-owned wrappers first
