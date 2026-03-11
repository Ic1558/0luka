#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
APP_DIR="$ROOT_DIR/repos/option"

cd "$APP_DIR"
exec dotenvx run -- ./venv/bin/python3 src/antigravity_prod.py
