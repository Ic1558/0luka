#!/usr/bin/env zsh
set -euo pipefail

REDIS="/opt/homebrew/bin/redis-cli"
JQ="/opt/homebrew/bin/jq"
HOST="127.0.0.1"
PORT="6379"
AUTH="gggclukaic"
CHAN_IN="shell"

echo "== shell-exec-stub: subscribe $CHAN_IN =="

$REDIS -h $HOST -p $PORT -a "$AUTH" --raw SUBSCRIBE "$CHAN_IN" | while read -r line; do
  if [[ "$line" == "message" ]]; then
    read -r chan
    read -r payload
    echo "-- incoming: $payload"

    tid=$(echo "$payload" | $JQ -r '.task_id // empty')
    cmd=$(echo "$payload" | $JQ -r '.cmd // empty')
    [[ -z "$tid" || -z "$cmd" ]] && { echo "!! missing task_id/cmd"; continue; }

    # รันคำสั่งอย่างปลอดภัย (จับ stdout/stderr และ exit code)
    out="$(eval "$cmd" 2>&1)"; rc=$?

    resp=$($JQ -n \
      --arg tid "$tid" \
      --arg out "$out" \
      --argjson rc "$rc" \
      '{task_id:$tid, status: ( $rc==0 ? "ok":"error"), code:$rc, output:$out}')

    # publish กลับไปยังช่อง response ตาม task_id
    $REDIS -h $HOST -p $PORT -a "$AUTH" PUBLISH "shell:response:$tid" "$resp" >/dev/null
    echo ">> replied to shell:response:$tid (rc=$rc)"
  fi
done
