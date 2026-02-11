#!/usr/bin/env zsh
set -euo pipefail

REPO="$HOME/Library/CloudStorage/GoogleDrive-ittipong.c@gmail.com/My Drive/02luka/02luka-repo"

mkdir -p "$REPO/.devcontainer" "$REPO/config" "$REPO/.cache/npm" "$REPO/.cache/node" "$REPO/.cache/pip" "$REPO/.cache/playwright" "$REPO/.cache/misc"

cat > "$REPO/.devcontainer/devcontainer.json" <<'JSON'
{ "name": "02Luka Dev",
  "image": "mcr.microsoft.com/devcontainers/base:ubuntu",
  "remoteUser": "vscode",
  "features": {},
  "customizations": { "vscode": {
      "settings": { "terminal.integrated.defaultProfile.linux": "zsh", "files.eol": "\n" },
      "extensions": [ "ms-vscode.makefile-tools", "esbenp.prettier-vscode" ]
  }},
  "mounts": [
    "source=${localWorkspaceFolder}/.cache/npm,target=/home/vscode/.npm,type=bind",
    "source=${localWorkspaceFolder}/.cache/node,target=/home/vscode/.cache/node,type=bind",
    "source=${localWorkspaceFolder}/.cache/pip,target=/home/vscode/.cache/pip,type=bind",
    "source=${localWorkspaceFolder}/.cache/playwright,target=/home/vscode/.cache/ms-playwright,type=bind",
    "source=${localWorkspaceFolder}/.cache/misc,target=/home/vscode/.cache/misc,type=bind"
  ],
  "postCreateCommand": "mkdir -p ~/.npm ~/.cache/node ~/.cache/pip ~/.cache/ms-playwright ~/.cache/misc"
}
JSON

cat > "$REPO/config/phase6_thresholds.json" <<'JSON'
{
  "docker": { "disk_cap_gb": 60, "warn_pct": 75, "crit_pct": 85 },
  "alerts": { "cooldown_sec": 3600 },
  "notes": "If Docker Desktop cap changes, update disk_cap_gb to match."
}
JSON

echo "✅ Wrote .devcontainer/devcontainer.json and config/phase6_thresholds.json"
