#!/bin/sh
# Daily backup script for Datakult
# This script is designed to be run by cron daily

set -e

# Change to app directory
# In production (Docker), this will be /app
# In dev, we need to find the script's directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# If /app exists and contains manage.py, use it (production)
# Otherwise use the project directory (dev)
if [ -f "/app/src/manage.py" ]; then
    cd /app || { echo "Error: Failed to change directory to /app" >&2; exit 1; }
else
    cd "$PROJECT_DIR" || { echo "Error: Failed to change directory to $PROJECT_DIR" >&2; exit 1; }
fi

# Run the auto_backup command which creates a backup and rotates old ones
# Use manage.py directly instead of poe to avoid requiring dev dependencies in production
if [ -f "/app/src/manage.py" ]; then
    uv run /app/src/manage.py auto_backup --keep 7
else
    uv run "$PROJECT_DIR/src/manage.py" auto_backup --keep 7
fi

echo "Daily backup completed at $(date)"
