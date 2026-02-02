#!/usr/bin/env zsh
# SOURCE-OF-TRUTH: $HOME/0luka/interface/frontends/raycast/atg_multi_snap_copy.zsh
# @raycast.schemaVersion 1
# @raycast.title ATG Multi Snapshot (Copy)
# @raycast.mode silent
# @raycast.packageName 0luka
# @raycast.icon 📋
# @raycast.description v2.1.2: digest + copy (no raw logs), use --full for deep
# @raycast.needsConfirmation false

set -euo pipefail
export LC_ALL=en_US.UTF-8

exec "/Users/icmini/0luka/interface/frontends/raycast/atg_multi_snap.zsh" --copy "$@"
