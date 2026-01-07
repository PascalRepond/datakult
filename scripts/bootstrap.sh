#!/bin/bash
# Bootstrap script for Datakult project.
#
# This script installs the project from scratch, assuming only `uv` and `npm` are installed.
# It is IDEMPOTENT: running it multiple times is safe and won't destroy existing data.
#
# It handles:
# 1. Python dependencies (via uv)
# 2. Node.js dependencies for Tailwind CSS
# 3. Tailwind CSS build
# 4. Static files collection
# 5. Database migrations
# 6. Default superuser creation (if not exists)
#
# Usage:
#   ./scripts/bootstrap.sh
#
# Prerequisites:
#   - uv (https://docs.astral.sh/uv/)
#   - Node.js and npm (for Tailwind CSS)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

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

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

echo "=================================================="
echo "🚀 Datakult Bootstrap"
echo "=================================================="

# -----------------------------------------------------------------------------
# 1. Check prerequisites
# -----------------------------------------------------------------------------
print_step "Checking prerequisites..."

# Check uv
if ! command -v uv &> /dev/null; then
    print_error "uv is not installed."
    echo "Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi
print_success "uv found: $(uv --version)"

# Check Python version (managed by uv via .python-version)
PYTHON_VERSION=$(uv run python --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
REQUIRED_PYTHON_MAJOR=3
REQUIRED_PYTHON_MINOR=12

PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d'.' -f2)

if [ "$PYTHON_MAJOR" -lt "$REQUIRED_PYTHON_MAJOR" ] || \
   ([ "$PYTHON_MAJOR" -eq "$REQUIRED_PYTHON_MAJOR" ] && [ "$PYTHON_MINOR" -lt "$REQUIRED_PYTHON_MINOR" ]); then
    print_error "Python $REQUIRED_PYTHON_MAJOR.$REQUIRED_PYTHON_MINOR or higher is required, but found $PYTHON_VERSION"
    echo "uv should automatically install the correct version based on .python-version"
    exit 1
fi
print_success "Python $PYTHON_VERSION found (required: >=$REQUIRED_PYTHON_MAJOR.$REQUIRED_PYTHON_MINOR)"

# Check Node.js/npm
if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed."
    echo "Install Node.js 20+ from: https://nodejs.org/"
    echo "Or use nvm: https://github.com/nvm-sh/nvm"
    exit 1
fi

if ! command -v npm &> /dev/null; then
    print_error "npm is not installed."
    echo "Install Node.js from: https://nodejs.org/"
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+')
NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d'.' -f1)
REQUIRED_NODE_MAJOR=20

if [ "$NODE_MAJOR" -lt "$REQUIRED_NODE_MAJOR" ]; then
    print_error "Node.js $REQUIRED_NODE_MAJOR or higher is required, but found $NODE_VERSION"
    echo "Install Node.js 20+ from: https://nodejs.org/"
    echo "Or use nvm: nvm install 20 && nvm use 20"
    exit 1
fi
print_success "Node.js $NODE_VERSION found (required: >=$REQUIRED_NODE_MAJOR)"
print_success "npm $(npm --version) found"

# Check for gettext (optional but recommended for translations)
if ! command -v msgfmt &> /dev/null; then
    print_warning "gettext is not installed (optional, needed for translations)"
    echo "    Install with: apt-get install gettext (Debian/Ubuntu)"
    echo "    or: brew install gettext (macOS)"
else
    print_success "gettext found"
fi

# -----------------------------------------------------------------------------
# 2. Install Python dependencies
# -----------------------------------------------------------------------------
print_step "Installing Python dependencies..."

cd "$PROJECT_ROOT"
uv sync

print_success "Python dependencies installed"

# -----------------------------------------------------------------------------
# 3. Install Node.js dependencies (for Tailwind CSS)
# -----------------------------------------------------------------------------
print_step "Installing Node.js dependencies..."

cd "$PROJECT_ROOT/src/theme/static_src"

if [ ! -d "node_modules" ]; then
    npm install
    print_success "Node.js dependencies installed"
else
    print_warning "node_modules already exists, skipping npm install"
    echo "    Run 'npm install' manually in src/theme/static_src/ to update"
fi

cd "$PROJECT_ROOT"

# -----------------------------------------------------------------------------
# 4. Build Tailwind CSS
# -----------------------------------------------------------------------------
print_step "Building Tailwind CSS..."

cd "$PROJECT_ROOT/src/theme/static_src"
npm run build
cd "$PROJECT_ROOT"

print_success "Tailwind CSS built"

# -----------------------------------------------------------------------------
# 5. Collect static files
# -----------------------------------------------------------------------------
print_step "Collecting static files..."

uv run poe collectstatic

print_success "Static files collected"

# -----------------------------------------------------------------------------
# 6. Apply database migrations
# -----------------------------------------------------------------------------
print_step "Applying database migrations..."

uv run poe migrate

print_success "Migrations applied"

# -----------------------------------------------------------------------------
# 7. Compile translation messages
# -----------------------------------------------------------------------------
print_step "Compiling translation messages..."

if command -v msgfmt &> /dev/null; then
    uv run poe compilemessages
    print_success "Translation messages compiled"
else
    print_warning "Skipping translation compilation (gettext not installed)"
    echo "    Translations will not work until you install gettext and run:"
    echo "    uv run poe compilemessages"
fi

# -----------------------------------------------------------------------------
# 8. Create default superuser (if not exists)
# -----------------------------------------------------------------------------
print_step "Checking superuser..."

# Check if admin user exists using a Python script
ADMIN_EXISTS=$(uv run python -c "
import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import sys
sys.path.insert(0, '$PROJECT_ROOT/src')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
print('yes' if User.objects.filter(username='admin').exists() else 'no')
" 2>/dev/null)

if [ "$ADMIN_EXISTS" = "yes" ]; then
    print_warning "Superuser 'admin' already exists, skipping creation"
else
    DJANGO_SUPERUSER_PASSWORD=admin uv run ./src/manage.py createsuperuser \
        --username admin \
        --email admin@example.com \
        --noinput
    print_success "Superuser created: admin / admin"
fi

# -----------------------------------------------------------------------------
# Done!
# -----------------------------------------------------------------------------
echo ""
echo "=================================================="
echo -e "${GREEN}✅ Bootstrap complete!${NC}"
echo "=================================================="
echo ""
echo "Start the development server with:"
echo "    uv run poe server"
echo ""
echo "Login with: admin / admin"
echo ""
echo "To load sample development data, run:"
echo "    uv run poe setup"
echo ""
echo "Other useful commands:"
echo "    uv run poe test      # Run tests"
echo "    uv run poe ci        # Run all quality checks"
