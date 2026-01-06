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

# Start the server
echo "Starting server..."
exec "$@"
