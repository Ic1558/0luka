#!/usr/bin/env zsh
set -eu

dest="$HOME/Desktop/ram-kernel-pack_$(date +%y%m%d_%H%M)"
mkdir -p "$dest"

pushd /Library/Logs/DiagnosticReports >/dev/null

cp -f \
  com.apple.Virtualization.VirtualMachine_2025-11-02-001243_Ittipongs-Mac-mini.diag \
  mds_stores_2025-11-01-233642_Ittipongs-Mac-mini.diag \
  fileproviderd_2025-11-02-015143_Ittipongs-Mac-mini.cpu_resource.diag \
  diskimagesiod_2025-11-01-234547_Ittipongs-Mac-mini.diag \
  backupd_2025-11-01-214201_Ittipongs-Mac-mini.diag \
  ChatGPT_2025-11-01-182611_Ittipongs-Mac-mini.cpu_resource.diag \
  Google\ Drive_2025-10-31-210729_Ittipongs-Mac-mini.diag \
  Safari_2025-10-31-193718_Ittipongs-Mac-mini.cpu_resource.diag \
  logd_2025-11-01-064534_Ittipongs-Mac-mini.diag \
  "$dest" 2>/dev/null || true

# Optional candidates (ถ้ามีให้ก๊อปด้วย)
for f in shutdown_stall_2025-10-31-201302_Ittipongs-Mac-mini.shutdownStall \
         panic-full-*.ips Kernel_*; do
  [[ -e "$f" ]] && cp -f "$f" "$dest"
done

# JetsamEvent
[[ -e Retired/JetsamEvent-2025-10-31-220920.ips ]] && cp -f Retired/JetsamEvent-2025-10-31-220920.ips "$dest"

popd >/dev/null

# Wi-Fi chip traps (อาจไม่ใช่สาเหตุ RAM แต่แนบไว้)
mkdir -p "$dest/CoreCapture_WiFi"
cp -Rf /Library/Logs/CrashReporter/CoreCapture/WiFi/* "$dest/CoreCapture_WiFi" 2>/dev/null || true

# แนบ memwatch CSV ถ้ามี
ls -1 ~/02luka_memwatch_*.csv 2>/dev/null | tail -n 1 | xargs -I{} cp "{}" "$dest" 2>/dev/null || true

zip -yr "$dest.zip" "$dest" >/dev/null
echo "Packed: $dest.zip"
open -R "$dest.zip"
