#!/bin/zsh
# system/tools/ops/rotate_logs.zsh
# Phase F: Log Rotation (F1)
# Rotates logs in logs/components/**/* exceeding 10MB.
# Retention: 7 rotated logs (.1 to .7).

# 1. Config
MAX_SIZE=10000000 # 10MB
RETENTION=7
ROOT="/Users/icmini/0luka"
AUDIT_LOG="logs/ops/rotation.log"

mkdir -p "$ROOT/logs/ops"

log_event() {
    echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ") | $1" >> "$ROOT/$AUDIT_LOG"
}

# 2. Check ROOT integrity
if [[ ! -f "$ROOT/luka.md" ]]; then
    echo "FATAL: Invalid ROOT $ROOT"
    exit 1
fi

# 3. Iterate over component logs
find "$ROOT/logs/components" -name "current.log" -type f | while read -r log_path; do
    # Get size in bytes (macOS stat)
    actual_size=$(stat -f%z "$log_path" 2>/dev/null || echo 0)
    
    if [[ $actual_size -gt $MAX_SIZE ]]; then
        echo "Rotating ${log_path#$ROOT/} (Size: $actual_size bytes)"
        
        # 3.1 Shift: 6 -> 7, 5 -> 6 ... 1 -> 2
        for i in $(seq $((RETENTION - 1)) -1 1); do
            source_log="$log_path.$i"
            dest_log="$log_path.$((i + 1))"
            if [[ -f "$source_log" ]]; then
                mv "$source_log" "$dest_log"
            fi
        done
        
        # 3.2 Rotate current: target -> target.1
        mv "$log_path" "$log_path.1"
        
        # 3.3 Re-init current
        touch "$log_path"
        chmod 644 "$log_path"
        
        log_event "ROTATED: ${log_path#$ROOT/} (Size: $actual_size bytes)"
    fi
done

echo "✅ Log rotation check complete."
