#!/usr/bin/env bash
set -euo pipefail
LUKA_HOME="${LUKA_HOME:-/Users/icmini/LocalProjects/02luka_local_g/g}"
INBOX="$LUKA_HOME/bridge/inbox/CLC"; WOHIST="$LUKA_HOME/logs/wo_drop_history"
mkdir -p "$INBOX" "$WOHIST"; URL="${LUKA_OTA_URL:-}"; SHA_EXPECTED="${LUKA_OTA_SHA256:-}"; LOCAL="${1:-}"
have(){ command -v "$1" >/dev/null 2>&1; }
dl(){ curl -fsSL "$1" -o "$2"; }
sha_ok(){ local f="$1" w="$2" g; if have shasum; then g="$(shasum -a256 "$f"|awk '{print$1}')"; elif have sha256sum; then g="$(sha256sum "$f"|awk '{print$1}')"; else return 0; fi; [[ -z "$w" || "$g" == "$w" ]]; }
T="$(mktemp)"; SRC=""
if [[ -n "$URL" ]]; then dl "$URL" "$T"; [[ -s "$T" ]] || { echo "empty"; exit 2; }
  grep -q '"kind"' "$T" || { echo "not WO"; exit 2; }; [[ -z "$SHA_EXPECTED" ]] || sha_ok "$T" "$SHA_EXPECTED" || { echo "SHA mismatch"; exit 2; }
  SRC="$T"
elif [[ -n "$LOCAL" ]]; then [[ -f "$LOCAL" ]] || { echo "not found"; exit 2; } ; cp "$LOCAL" "$T"; SRC="$T"
else echo "usage: LUKA_OTA_URL=... $0  |  $0 /path/wo.json"; exit 2; fi
ID="WO-$(date +%s)-ota"; DEST="$INBOX/$ID.json"; mv "$SRC" "$DEST"; cp "$DEST" "$WOHIST/${ID}_drop.json" 2>/dev/null || true; echo "Dropped WO: $DEST"