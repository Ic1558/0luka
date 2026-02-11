#!/usr/bin/env zsh
while :; do
  printf "\n[%s] RAM snapshot\n" "$(date '+%F %T')"
  ps -axo pid,ppid,rss,comm | awk '{$2=$2; printf "%7s %7s %6.1f MB  %s\n",$1,$2,$3/1024,$4}' \
    | sort -k3 -nr | head -15
  vm_stat | awk 'BEGIN{pagesize=4096}/Pages (active|wired|free|purgeable)/{gsub("[^0-9]","",$3);printf "%-12s %7.1f MB\n",$2,$3*4096/1024/1024}'
  sleep 300
done
