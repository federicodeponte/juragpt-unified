#!/bin/bash
#
# Production wrapper for incremental corpus updates.
#
# Features:
# - Lock file to prevent concurrent runs
# - Log rotation (keeps last 30 days)
# - Email notifications on failure (optional)
# - Exit codes for monitoring
#
# Usage:
#   # Run update manually
#   ./scripts/run_update.sh
#
#   # Add to crontab for daily updates at 2 AM
#   0 2 * * * /path/to/juragpt-rag/scripts/run_update.sh
#

set -euo pipefail

# ===== CONFIGURATION =====

# Project root directory (auto-detected)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Python environment
VENV_PATH="$PROJECT_ROOT/venv"
PYTHON="$VENV_PATH/bin/python"

# Logging
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/update_$(date +%Y%m%d_%H%M%S).log"
LOCK_FILE="$PROJECT_ROOT/data/update.lock"

# Email notifications (optional - set EMAIL to enable)
EMAIL="${JURAGPT_ALERT_EMAIL:-}"  # Set JURAGPT_ALERT_EMAIL env var to enable
SENDMAIL="/usr/sbin/sendmail"

# ===== FUNCTIONS =====

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

error() {
    log "ERROR: $*"
}

send_email() {
    local subject="$1"
    local body="$2"

    if [[ -z "$EMAIL" ]]; then
        log "Email notifications disabled (JURAGPT_ALERT_EMAIL not set)"
        return 0
    fi

    if [[ ! -x "$SENDMAIL" ]]; then
        log "Sendmail not available at $SENDMAIL"
        return 0
    fi

    log "Sending email notification to $EMAIL"

    cat <<EOF | $SENDMAIL -t
To: $EMAIL
Subject: [JuraGPT] $subject
Content-Type: text/plain; charset=UTF-8

$body

---
Log file: $LOG_FILE
Hostname: $(hostname)
Time: $(date)
EOF
}

cleanup() {
    if [[ -f "$LOCK_FILE" ]]; then
        log "Releasing lock file"
        rm -f "$LOCK_FILE"
    fi
}

# ===== MAIN =====

main() {
    # Create log directory
    mkdir -p "$LOG_DIR"

    log "========================================"
    log "JuraGPT Corpus Update - Starting"
    log "========================================"
    log "Project root: $PROJECT_ROOT"
    log "Python: $PYTHON"
    log "Log file: $LOG_FILE"

    # Check if Python environment exists
    if [[ ! -f "$PYTHON" ]]; then
        error "Python virtual environment not found at $VENV_PATH"
        error "Run: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        exit 1
    fi

    # Acquire lock to prevent concurrent runs
    if [[ -f "$LOCK_FILE" ]]; then
        # Check if lock is stale (> 12 hours old)
        if [[ $(find "$LOCK_FILE" -mmin +720 2>/dev/null) ]]; then
            log "WARNING: Stale lock file found (>12 hours old), removing"
            rm -f "$LOCK_FILE"
        else
            error "Another update is already running (lock file exists: $LOCK_FILE)"
            log "If this is a stale lock, manually remove: rm $LOCK_FILE"
            exit 1
        fi
    fi

    # Create lock file
    echo $$ > "$LOCK_FILE"
    trap cleanup EXIT INT TERM

    # Change to project root
    cd "$PROJECT_ROOT"

    # Run update
    log "Starting incremental update..."

    START_TIME=$(date +%s)

    if $PYTHON scripts/update_corpus.py >> "$LOG_FILE" 2>&1; then
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))

        log "========================================"
        log "Update completed successfully"
        log "Duration: ${DURATION}s"
        log "========================================"

        # Show stats
        $PYTHON scripts/update_corpus.py --stats >> "$LOG_FILE" 2>&1

        exit_code=0
    else
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))

        error "========================================"
        error "Update FAILED"
        error "Duration: ${DURATION}s"
        error "========================================"

        # Send failure notification
        send_email "Corpus Update Failed" \
            "The incremental corpus update failed after ${DURATION}s.

Please check the log file for details:
$LOG_FILE

Last 50 lines of log:
$(tail -n 50 "$LOG_FILE")
"

        exit_code=1
    fi

    # Cleanup old logs (keep last 30 days)
    log "Cleaning up old logs (keeping last 30 days)..."
    find "$LOG_DIR" -name "update_*.log" -type f -mtime +30 -delete 2>/dev/null || true

    return $exit_code
}

# Run main function
main

exit $?
