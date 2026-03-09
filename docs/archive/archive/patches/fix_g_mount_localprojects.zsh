#!/usr/bin/env zsh
set -euo pipefail
ts(){ date +"%Y-%m-%d %H:%M:%S"; }

# 0) Paths
REPO="$HOME/Library/CloudStorage/GoogleDrive-ittipong.c@gmail.com/My Drive/02luka/02luka-repo"
LOCAL_BASE="$HOME/LocalProjects/02luka_local_g"
SRV_DIR_REL="g/tools/services"
mkdir -p "$LOCAL_BASE/$SRV_DIR_REL"

echo "$(ts) 🔧 Syncing service scripts into LocalProjects..."
rsync -avh --delete "$REPO/$SRV_DIR_REL/" "$LOCAL_BASE/$SRV_DIR_REL/"

# 1) Compose override: point /app/g -> LocalProjects (rw ชั่วคราวเพื่อ npm install)
OVR="$REPO/docker-compose.override.localprojects.yml"
cat > "$OVR" <<YML
services:
  http_redis_bridge:
    volumes:
      - "$LOCAL_BASE/g:/app/g:rw"
  clc_listener:
    volumes:
      - "$LOCAL_BASE/g:/app/g:rw"
  ops_health_watcher:
    volumes:
      - "$LOCAL_BASE/g:/app/g:ro"
YML
echo "$(ts) 📄 Wrote override: $OVR"

# 2) Restart services with override (เฉพาะ 2 ตัวแรกที่พัง)
cd "$REPO"
docker compose -f docker-compose.yml -f "$OVR" up -d http_redis_bridge clc_listener

# 3) Install redis ในคอนเทนเนอร์ (จะเขียนลง $LOCAL_BASE/g/node_modules)
echo "$(ts) 📦 npm install redis in containers..."
docker exec http_redis_bridge sh -lc 'cd /app/g && npm_config_package_lock=false npm i redis --no-save --no-audit --no-fund'
docker exec clc_listener      sh -lc 'cd /app/g && npm_config_package_lock=false npm i redis --no-save --no-audit --no-fund'

# 4) เปลี่ยนกลับเป็น :ro เพื่อเสถียรภาพ (ลดการเขียน)
cat > "$OVR" <<YML
services:
  http_redis_bridge:
    volumes:
      - "$LOCAL_BASE/g:/app/g:ro"
  clc_listener:
    volumes:
      - "$LOCAL_BASE/g:/app/g:ro"
  ops_health_watcher:
    volumes:
      - "$LOCAL_BASE/g:/app/g:ro"
YML
echo "$(ts) 🔒 Switched override mounts to :ro"

# Apply ro mounts
docker compose -f docker-compose.yml -f "$OVR" up -d http_redis_bridge clc_listener ops_health_watcher

# 5) Status
echo "$(ts) ✅ Done. Current status:"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Mounts}}' | sed -E 's/:rw|:ro//g'
echo "$(ts) ℹ️  If ok, keep using LocalProjects as stable source for /app/g."
