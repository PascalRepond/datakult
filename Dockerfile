# Stage 1: Build Tailwind CSS
FROM node:22-alpine AS tailwind-builder

# Reproduce the exact project structure for @source paths to work
WORKDIR /app/src

# Copy Tailwind source files
COPY src/theme/static_src/ ./theme/static_src/

# Copy files that Tailwind needs to scan for classes
COPY src/templates/ ./templates/
COPY src/core/ ./core/
COPY src/static/ ./static/

# Install dependencies and build
WORKDIR /app/src/theme/static_src
RUN npm ci
RUN npm run build

# Stage 2: Python application
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Production defaults for data persistence (can be overridden)
ENV DATABASE_PATH=/app/data/db.sqlite3
ENV MEDIA_ROOT=/app/data/media

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies (production only)
RUN uv sync --frozen --no-dev --group prod

# Copy application code
COPY src/ ./src/

# Copy built CSS from tailwind stage
COPY --from=tailwind-builder /app/src/theme/static/css/dist/ ./src/theme/static/css/dist/

# Create data directory for persistent storage (SQLite + media + backups)
RUN mkdir -p /app/data/media /app/data/backups

# Copy entrypoint script
COPY scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Compile translation messages
RUN uv run ./src/manage.py compilemessages

# Collect static files with production settings
# Set DEBUG=false to use CompressedManifestStaticFilesStorage during collectstatic
# This ensures the manifest file is created for production use
RUN DEBUG=false SECRET_KEY=build-time-only ALLOWED_HOSTS=localhost uv run ./src/manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

WORKDIR /app/src

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uv", "run", "gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--access-logfile", "-", "--error-logfile", "-"]
