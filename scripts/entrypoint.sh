#!/bin/bash
set -e

# Run migrations
echo "Running migrations..."
uv run python manage.py migrate --noinput

# Create superuser if it doesn't exist
echo "Checking for superuser..."
uv run python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
username = '${DJANGO_SUPERUSER_USERNAME:-admin}'
if not User.objects.filter(username=username).exists():
    User.objects.create_superuser(
        username=username,
        email='${DJANGO_SUPERUSER_EMAIL:-admin@example.com}',
        password='${DJANGO_SUPERUSER_PASSWORD:-admin}'
    )
    print(f'Superuser {username} created.')
else:
    print(f'Superuser {username} already exists.')
"

# Reload crontab to ensure it's active at runtime
echo "Reloading crontab..."
if [ -f /etc/cron.d/datakult-backup ]; then
    crontab /etc/cron.d/datakult-backup
    echo "✓ Crontab loaded"
else
    echo "✗ Warning: Crontab file not found"
fi

# Start cron in the background for daily backups
echo "Starting cron for daily backups..."
if cron; then
    echo "✓ Cron service started"
    # Verify cron is running
    sleep 1
    if pgrep cron > /dev/null; then
        echo "✓ Cron process confirmed running"
    else
        echo "✗ Warning: Cron process not found"
    fi
else
    echo "✗ Warning: Failed to start cron service"
fi

# Start the server
echo "Starting server..."
exec "$@"
