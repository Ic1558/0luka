#!/usr/bin/env zsh
out="$HOME/02luka_memwatch_$(date +%y%m%d_%H%M).csv"
echo "ts,phys_used_gb,wired_gb,swap_gb,top5" > "$out"
while :; do
  ts=$(date +%F_%T)
  used=$(vm_stat | awk '/Pages active|Pages inactive|Pages speculative|Pages wired/ {gsub("[^0-9]","",$3); s+=$3} END{printf "%.2f", s*4096/1024/1024/1024}')
  wired=$(vm_stat | awk '/Pages wired/ {gsub("[^0-9]","",$3); printf "%.2f", $3*4096/1024/1024/1024}')
  swap=$(sysctl -n vm.swapusage | awk '{print $7}')
  top5=$(ps -axo rss,comm | sort -nr | head -5 | awk '{printf "%.1fMB:%s ",$1/1024,$2}')
  echo "$ts,$used,$wired,$swap,\"$top5\"" >> "$out"
  sleep 60
done
