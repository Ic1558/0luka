# Manual: MBP Setup Menu (Human Control Plane)

## Purpose

Provide a small control-plane menu on MBP that can operate the mini over SSH and talk to OPAL HTTP API.

## Required Environment Variables

- `OPAL_API_BASE` (e.g. `http://<tailscale-ip>:7001`)
- `SSH_HOST_ALIAS` (your ssh config host alias, e.g. `macmini`)
- `OPAL_REMOTE_ROOT` (root path on mini, e.g. `~/0luka`)
- `OPAL_LOCAL_ARTIFACTS_DIR` (where artifacts are synced locally)

## Install

```bash
mkdir -p ~/.local/bin
chmod +x ~/.local/bin/setup
```

Ensure your PATH includes `~/.local/bin`.

## Run

```bash
setup
```

## Menu Behavior

1) SSH to mini
2) Status: hostname, uptime, disk
3) API health: `GET /api/health`
4) List jobs: `GET /api/jobs`
5) Tail logs: `runtime/logs/api_server.log` and recent `runtime/logs/worker_pool/*.log`
6) Rsync artifacts: `runtime/opal_artifacts/`
