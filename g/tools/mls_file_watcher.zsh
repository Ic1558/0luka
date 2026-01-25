#!/usr/bin/env zsh
# Shim to canonical tool
# Legacy path: g/tools/mls_file_watcher.zsh
# Canonical: tools/mls_file_watcher.zsh

exec "$(git rev-parse --show-toplevel)/tools/mls_file_watcher.zsh" "$@"
