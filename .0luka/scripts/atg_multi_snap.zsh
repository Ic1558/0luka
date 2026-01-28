#!/usr/bin/env zsh
# SOURCE-OF-TRUTH: $HOME/0luka/interface/frontends/raycast/atg_multi_snap.zsh
# DO NOT EDIT: shim that calls canonical script

set -euo pipefail

ROOT="${ROOT:-$HOME/0luka}"
exec "${ROOT}/interface/frontends/raycast/atg_multi_snap.zsh" "$@"
