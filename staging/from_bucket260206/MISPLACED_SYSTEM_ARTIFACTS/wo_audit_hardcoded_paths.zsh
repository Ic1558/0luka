#!/bin/zsh
# Comprehensive audit of hardcoded paths in 02luka system
# Scans LaunchAgents, scripts, and configs for hardcoded /Users/icmini/My Drive (ittipong.c@gmail.com) (1)/02luka paths

set -euo pipefail

echo "🔍 02LUKA HARDCODED PATH AUDIT - $(date)"
echo "========================================"

SOT="/Users/icmini/My Drive (ittipong.c@gmail.com) (1)/02luka"
OLD_PATH="/Users/icmini/My Drive (ittipong.c@gmail.com) (1)/02luka"
REPORT_FILE="${SOT}/c/reports/system/hardcoded_paths_audit_$(date +%y%m%d_%H%M%S).txt"

mkdir -p "${SOT}/c/reports/system"

echo "📁 SOT Path: $SOT"
echo "❌ Old Path: $OLD_PATH" 
echo "📄 Report: $REPORT_FILE"
echo

# Function to check file for hardcoded paths
check_file() {
    local file="$1"
    local issues=0
    
    if [[ -f "$file" ]]; then
        while IFS= read -r line; do
            if [[ "$line" == *"$OLD_PATH"* ]]; then
                echo "❌ HARDCODED: $file"
                echo "   Line: $line"
                ((issues++))
                echo "$file: $line" >> "$REPORT_FILE"
            fi
        done < "$file"
    fi
    return $issues
}

echo "🔍 SCANNING LAUNCHAGENTS..."
echo "============================"

total_issues=0
agent_issues=0

for plist in /Users/icmini/Library/LaunchAgents/com.02luka*.plist; do
    if [[ -f "$plist" ]]; then
        echo "Checking: $(basename "$plist")"
        if check_file "$plist"; then
            ((agent_issues++))
        fi
    fi
done

echo
echo "🔍 SCANNING CLOUDFLARE CONFIGS..."
echo "=================================="

for cf_file in /Users/icmini/.cloudflared/*.yml; do
    if [[ -f "$cf_file" ]]; then
        echo "Checking: $(basename "$cf_file")"
        check_file "$cf_file"
    fi
done

echo
echo "🔍 SCANNING SOT SCRIPTS..."
echo "=========================="

find "$SOT" -name "*.sh" -o -name "*.py" -o -name "*.zsh" | head -20 | while read -r script; do
    echo "Checking: $(basename "$script")"
    check_file "$script"
done

echo
echo "🔍 SCANNING FOR BROKEN SERVICE REFERENCES..."
echo "============================================="

failed_services=0
launchctl list | grep "02luka" | while read -r status pid label; do
    if [[ "$status" == "78" || "$status" == "-" ]]; then
        echo "❌ FAILED SERVICE: $label (exit $status)"
        ((failed_services++))
    fi
done

echo
echo "📊 AUDIT SUMMARY"
echo "================="
echo "LaunchAgent Issues: $agent_issues"
echo "Failed Services: $failed_services" 
echo "Report saved to: $REPORT_FILE"

if [[ $agent_issues -gt 0 ]]; then
    echo
    echo "🔧 RECOMMENDED ACTIONS:"
    echo "======================="
    echo "1. Update LaunchAgent paths to current SOT structure"
    echo "2. Migrate missing scripts to: $SOT/g/tools/"
    echo "3. Update log paths to: $SOT/logs/"
    echo "4. Reload fixed LaunchAgents"
fi

echo
echo "✅ Audit complete!"