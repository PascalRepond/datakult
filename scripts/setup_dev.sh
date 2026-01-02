#!/bin/bash
# Development data setup script.
#
# This script loads sample fixtures into an already installed project.
# WARNING: This is DESTRUCTIVE - it resets the database and media files!
#
# Use this to:
# - Reset your dev environment with fresh sample data
# - Start over with a clean database
#
# Prerequisites:
# - Run bootstrap.sh first to install dependencies
#
# Usage:
#   ./scripts/setup_dev.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DB_PATH="$PROJECT_ROOT/src/db.sqlite3"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "\n${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

echo "=================================================="
echo "🔄 Datakult Dev Data Setup"
echo "=================================================="
echo ""
echo -e "${YELLOW}⚠️  WARNING: This will reset the database and media files!${NC}"
echo ""
read -p "Continue? [y/N] " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# -----------------------------------------------------------------------------
# 1. Reset database
# -----------------------------------------------------------------------------
print_step "Resetting database..."

if [ -f "$DB_PATH" ]; then
    rm "$DB_PATH"
    print_success "Deleted existing database"
else
    print_warning "No existing database found"
fi

# -----------------------------------------------------------------------------
# 2. Clear media folder
# -----------------------------------------------------------------------------
print_step "Clearing media folder..."

MEDIA_DIR="$PROJECT_ROOT/src/media"
if [ -d "$MEDIA_DIR" ]; then
    rm -rf "${MEDIA_DIR:?}"/*
    print_success "Media folder cleared"
else
    mkdir -p "$MEDIA_DIR"
    print_warning "Media folder created"
fi

# -----------------------------------------------------------------------------
# 3. Apply migrations (recreate database schema)
# -----------------------------------------------------------------------------
print_step "Applying migrations..."

uv run poe migrate

print_success "Migrations applied"

# -----------------------------------------------------------------------------
# 4. Create superuser
# -----------------------------------------------------------------------------
print_step "Creating superuser..."

DJANGO_SUPERUSER_PASSWORD=admin uv run ./src/manage.py createsuperuser \
    --username admin \
    --email admin@example.com \
    --noinput

print_success "Superuser created: admin / admin"

# -----------------------------------------------------------------------------
# 5. Copy fixture cover images to media folder
# -----------------------------------------------------------------------------
print_step "Copying cover images..."

FIXTURES_COVERS="$PROJECT_ROOT/src/core/fixtures/covers"
MEDIA_COVERS="$PROJECT_ROOT/src/media/covers"

mkdir -p "$MEDIA_COVERS"

if [ -d "$FIXTURES_COVERS" ] && [ "$(ls -A "$FIXTURES_COVERS" 2>/dev/null)" ]; then
    cp "$FIXTURES_COVERS"/* "$MEDIA_COVERS"/
    print_success "Cover images copied"
else
    print_warning "No cover images found in fixtures"
fi

# -----------------------------------------------------------------------------
# 6. Load fixtures
# -----------------------------------------------------------------------------
print_step "Loading fixtures..."

uv run ./src/manage.py loaddata sample_data

print_success "Fixtures loaded"

# -----------------------------------------------------------------------------
# 7. Regenerate rendered reviews
# -----------------------------------------------------------------------------
print_step "Regenerating rendered reviews..."

uv run ./src/manage.py regenerate_reviews

print_success "Rendered reviews regenerated"

# -----------------------------------------------------------------------------
# Done!
# -----------------------------------------------------------------------------
echo ""
echo "=================================================="
echo -e "${GREEN}✅ Dev data setup complete!${NC}"
echo "=================================================="
echo ""
echo "Start the development server with:"
echo "    uv run poe server"
echo ""
echo "Login with: admin / admin"
