#!/bin/bash
#
# Resource monitoring script for long-running ingestion processes.
#
# Monitors RAM and disk usage, kills process if thresholds exceeded.
# Designed to prevent VM crashes during large-scale data ingestion.
#
# Usage:
#   # Monitor a specific process
#   ./scripts/monitor_resources.sh <PID>
#
#   # Monitor current Python ingestion
#   ./scripts/monitor_resources.sh $(pgrep -f "python.*ingest.py")
#

set -euo pipefail

# ===== CONFIGURATION =====

# Resource thresholds
MAX_RAM_PERCENT=85        # Kill if RAM usage > 85%
MAX_DISK_PERCENT=90       # Warn if disk usage > 90%
MIN_FREE_DISK_GB=50       # Kill if free disk < 50GB

# Monitoring interval
CHECK_INTERVAL_SEC=30     # Check every 30 seconds

# Logging
LOG_FILE="logs/resource_monitor.log"

# ===== FUNCTIONS =====

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    log "ERROR: $*"
}

get_ram_usage_percent() {
    # Get RAM usage percentage
    free | grep Mem | awk '{printf "%.0f", ($3/$2) * 100}'
}

get_disk_usage_percent() {
    # Get disk usage percentage for /home partition
    df /home | tail -1 | awk '{print $5}' | sed 's/%//'
}

get_free_disk_gb() {
    # Get free disk space in GB
    df /home | tail -1 | awk '{printf "%.0f", $4/1024/1024}'
}

get_process_mem_mb() {
    local pid=$1
    # Get process memory in MB (RSS)
    ps -p "$pid" -o rss= 2>/dev/null | awk '{printf "%.0f", $1/1024}' || echo "0"
}

kill_process_gracefully() {
    local pid=$1
    local reason="$2"

    error "Killing process $pid: $reason"

    # Try SIGTERM first (graceful)
    kill -TERM "$pid" 2>/dev/null || true
    sleep 5

    # Force kill if still running
    if ps -p "$pid" > /dev/null 2>&1; then
        error "Process still running, forcing kill..."
        kill -KILL "$pid" 2>/dev/null || true
    fi

    log "Process killed successfully"
}

# ===== MAIN =====

main() {
    # Validate arguments
    if [ $# -ne 1 ]; then
        echo "Usage: $0 <PID>"
        echo ""
        echo "Example:"
        echo "  $0 12345"
        echo "  $0 \$(pgrep -f 'python.*ingest.py')"
        exit 1
    fi

    local target_pid=$1

    # Validate PID exists
    if ! ps -p "$target_pid" > /dev/null 2>&1; then
        error "Process $target_pid does not exist"
        exit 1
    fi

    # Create log directory
    mkdir -p "$(dirname "$LOG_FILE")"

    log "========================================"
    log "Resource Monitor Started"
    log "========================================"
    log "Target PID: $target_pid"
    log "Process: $(ps -p "$target_pid" -o comm=)"
    log "RAM threshold: ${MAX_RAM_PERCENT}%"
    log "Disk threshold: ${MAX_DISK_PERCENT}%"
    log "Min free disk: ${MIN_FREE_DISK_GB}GB"
    log "Check interval: ${CHECK_INTERVAL_SEC}s"
    log "========================================"

    # Monitoring loop
    while true; do
        # Check if process still exists
        if ! ps -p "$target_pid" > /dev/null 2>&1; then
            log "Process $target_pid has exited - stopping monitor"
            exit 0
        fi

        # Get current resource usage
        ram_percent=$(get_ram_usage_percent)
        disk_percent=$(get_disk_usage_percent)
        free_disk_gb=$(get_free_disk_gb)
        process_mem_mb=$(get_process_mem_mb "$target_pid")

        # Log status
        log "Status: RAM=${ram_percent}% | Disk=${disk_percent}% | Free=${free_disk_gb}GB | Process=${process_mem_mb}MB"

        # Check RAM threshold
        if [ "$ram_percent" -gt "$MAX_RAM_PERCENT" ]; then
            kill_process_gracefully "$target_pid" "RAM usage exceeded ${MAX_RAM_PERCENT}% (current: ${ram_percent}%)"
            exit 1
        fi

        # Check disk space (free GB)
        if [ "$free_disk_gb" -lt "$MIN_FREE_DISK_GB" ]; then
            kill_process_gracefully "$target_pid" "Free disk space below ${MIN_FREE_DISK_GB}GB (current: ${free_disk_gb}GB)"
            exit 1
        fi

        # Warn on high disk usage (but don't kill)
        if [ "$disk_percent" -gt "$MAX_DISK_PERCENT" ]; then
            error "WARNING: Disk usage high: ${disk_percent}% (threshold: ${MAX_DISK_PERCENT}%)"
        fi

        # Sleep before next check
        sleep "$CHECK_INTERVAL_SEC"
    done
}

# Run main function
main "$@"
