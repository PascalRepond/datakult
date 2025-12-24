# Datakult 📚🎮🎬

A Django application to track and rate the media I consume: movies, TV shows, books, video games, music, and more.

> **Note:** This is a personal project, partly vibe-coded with the help of LLMs. It serves as a learning playground for Django, and to use as a personal tool.

## Features

- Track different media types (books, films, TV series, games, music, podcasts...)
- Rating system (1-10 scale)
- Markdown reviews
- Filters by type, status, year...

## Tech Stack

- **Backend**: Django 6 + Python 3.14
- **Frontend**: HTMX + Tailwind CSS + daisyUI
- **Database**: SQLite

## Getting Started

```bash
# Clone the repository
git clone https://github.com/PascalRepond/datakult.git
cd datakult

# Install dependencies (using uv)
uv sync

# Initial setup
uv run poe bootstrap

# Start the development server
uv run poe server
# The default superuser is admin/admin

```

## Available Commands

```bash
uv run poe server          # Dev server with Tailwind hot-reload
uv run poe migrate         # Apply migrations
uv run poe makemigrations  # Create migrations
uv run poe test            # Run tests
uv run poe lint            # Check code with Ruff
uv run poe format          # Format code
uv run poe ci              # Run all checks (format, lint, tests, audits)
```

## Project Structure

```
src/
├── config/     # Django settings
├── core/       # Main app (Media models, views, etc.)
├── accounts/   # User management
├── templates/  # HTML templates
├── static/     # CSS, JS, images
└── theme/      # Tailwind configuration
```

## Docker Deployment

### Quick Start (using pre-built image)

Download [docker-compose.prod.yml](docker-compose.prod.yml) and run:

```bash
# Download the compose file
curl -O https://raw.githubusercontent.com/PascalRepond/datakult/main/docker-compose.prod.yml

# Edit environment variables (especially SECRET_KEY and passwords)
nano docker-compose.prod.yml

# Start
docker compose -f docker-compose.prod.yml up -d
```

The application will be available at `http://localhost:8000`.  
Default credentials: `admin` / `admin`

Migrations and superuser creation are handled automatically on first start.

### Build from source

```bash
docker compose up -d
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | (insecure default) | Django secret key |
| `DEBUG` | `false` | Enable debug mode |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated list of allowed hosts |
| `DATABASE_PATH` | `src/db.sqlite3` | Path to SQLite database file |
| `MEDIA_ROOT` | `src/media` | Path to uploaded media files |
| `DJANGO_SUPERUSER_USERNAME` | `admin` | Default superuser username |
| `DJANGO_SUPERUSER_EMAIL` | `admin@example.com` | Default superuser email |
| `DJANGO_SUPERUSER_PASSWORD` | `admin` | Default superuser password |

## License

AGPL-3.0
