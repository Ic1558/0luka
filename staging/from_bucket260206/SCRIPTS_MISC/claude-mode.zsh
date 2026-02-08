#!/usr/bin/env zsh
set -euo pipefail

CFG_DIR="$HOME/.claude"
CFG="$CFG_DIR/settings.json"
PROXY="$CFG_DIR/settings.proxy.json"
NATIVE="$CFG_DIR/settings.native.json"

mkdir -p "$CFG_DIR"

if [[ ! -f "$PROXY" ]]; then
  cp -f "$CFG" "$PROXY"
  echo "[ok] saved proxy profile"
fi

if [[ ! -f "$NATIVE" ]]; then
  python3 << PY
import json, os
cfg=os.path.expanduser("~/.claude/settings.json")
native=os.path.expanduser("~/.claude/settings.native.json")
with open(cfg,"r") as f: c=json.load(f)
c.pop("env", None)
c["preferredModel"]="claude-sonnet-4-5-thinking"
with open(native,"w") as f: json.dump(c,f,indent=2)
print("[ok] created native profile")
PY
fi

mode="${1:-}"
if [[ "$mode" == "proxy" ]]; then
  cp -f "$PROXY" "$CFG"
  echo "[switched] claude => PROXY"
elif [[ "$mode" == "native" ]]; then
  cp -f "$NATIVE" "$CFG"
  echo "[switched] claude => NATIVE"
else
  echo "usage: claude-mode.zsh [proxy|native]"
fi
