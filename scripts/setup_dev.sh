#!/bin/bash
# Development environment setup script.
#
# This script:
# 1. Resets the database and local media folder
# 2. Applies all migrations
# 3. Creates an admin superuser (admin/admin)
# 4. Loads sample data fixtures

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DB_PATH="$PROJECT_ROOT/src/db.sqlite3"

echo "=================================================="
echo "Dev environment setup"
echo "=================================================="

# 1. Reset database
echo ""
echo "🗑️  Resetting database..."
if [ -f "$DB_PATH" ]; then
    rm "$DB_PATH"
    echo "   ✅ Deleted existing database: $DB_PATH"
else
    echo "   ℹ️  No existing database found."
fi

# 2. Clear media folder
echo ""
echo "🗑️  Clearing media folder..."
MEDIA_DIR="$PROJECT_ROOT/src/media"
if [ -d "$MEDIA_DIR" ]; then
    rm -rf "$MEDIA_DIR"/*
    echo "   ✅ Media folder cleared."
else
    echo "   ℹ️  No media folder found."
fi

# 3. Apply migrations
echo ""
echo "📦 Applying migrations..."
uv run poe migrate

# 4. Create superuser
echo ""
echo "👤 Creating superuser..."
DJANGO_SUPERUSER_PASSWORD=admin uv run ./src/manage.py createsuperuser \
    --username admin \
    --email admin@example.com \
    --noinput
echo "   ✅ Superuser created: admin/admin"

# 5. Copy fixture cover images to media folder
echo ""
echo "🖼️  Copying cover images..."
FIXTURES_COVERS="$PROJECT_ROOT/src/core/fixtures/covers"
MEDIA_COVERS="$PROJECT_ROOT/src/media/covers"

mkdir -p "$MEDIA_COVERS"

cp "$FIXTURES_COVERS"/* "$MEDIA_COVERS"/
echo "   ✅ Cover images copied to $MEDIA_COVERS"

# 6. Load fixtures
echo ""
echo "📚 Loading fixtures..."
uv run ./src/manage.py loaddata sample_data
echo "   ✅ Fixtures loaded successfully."

echo ""
echo "=================================================="
echo "✅ Setup complete!"
echo "=================================================="
echo ""
echo "You can now start the server:"
echo "  uv run poe server"
echo ""
echo "Login with: admin / admin"
