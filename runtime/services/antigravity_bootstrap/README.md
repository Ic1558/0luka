# Antigravity Runtime Bootstrap

This directory contains the 0luka runtime-owned PM2/bootstrap wrapper for the
current Antigravity services.

Ownership:

- bootstrap wrapper: `runtime/services/antigravity_bootstrap/pm2_start.zsh`
- service wrappers:
  - `runtime/services/antigravity_scan/runner.zsh`
  - `runtime/services/antigravity_realtime/runner.zsh`

Legacy repo-local deploy scripts may remain discoverable, but runtime bootstrap
ownership now points first to this 0luka path.
