#!/bin/sh
# Daily backup script for Datakult
# This script is designed to be run by cron daily
#
# Features:
# - Creates daily backups and rotates old ones
# - Logs all output to /var/log/cron.log
# - Sends error notifications to stderr and log file
# - Returns non-zero exit code on failure

# Function to log errors
log_error() {
    echo "❌ ERROR [$(date '+%Y-%m-%d %H:%M:%S')]: $1" >&2
    echo "❌ ERROR [$(date '+%Y-%m-%d %H:%M:%S')]: $1" >> /var/log/backup-errors.log 2>/dev/null || true
}

# Function to log info
log_info() {
    echo "ℹ️  [$(date '+%Y-%m-%d %H:%M:%S')]: $1"
}

log_info "Starting daily backup process"

# Change to app directory
# In production (Docker), this will be /app
# In dev, we need to find the script's directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# If /app exists and contains manage.py, use it (production)
# Otherwise use the project directory (dev)
if [ -f "/app/src/manage.py" ]; then
    log_info "Running in production mode (/app)"
    cd /app || {
        log_error "Failed to change directory to /app"
        exit 1
    }
    MANAGE_CMD="uv run /app/src/manage.py"
else
    log_info "Running in development mode ($PROJECT_DIR)"
    cd "$PROJECT_DIR" || {
        log_error "Failed to change directory to $PROJECT_DIR"
        exit 1
    }
    MANAGE_CMD="uv run $PROJECT_DIR/src/manage.py"
fi

# Verify uv is available
if ! command -v uv >/dev/null 2>&1; then
    log_error "uv command not found in PATH"
    exit 1
fi

# Run the auto_backup command which creates a backup and rotates old ones
log_info "Executing backup command: $MANAGE_CMD auto_backup --keep 7"

if $MANAGE_CMD auto_backup --keep 7; then
    log_info "✅ Daily backup completed successfully at $(date)"
    exit 0
else
    EXIT_CODE=$?
    log_error "Backup command failed with exit code $EXIT_CODE"
    log_error "Check Django logs for more details"
    exit $EXIT_CODE
fi
