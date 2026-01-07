<a id="readme-top"></a>

[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![GPL-3.0][license-shield]][license-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/PascalRepond/datakult">
    <img src="src/static/images/bookshelf.png" alt="Datakult logo (icon by Freepik - Flaticon)" width="80" height="80">
  </a>

<h3 align="center">Datakult</h3>

  <p align="center">
    Review and analyse the media and culture that you consume.
  </p>
</div>

<!-- ABOUT THE PROJECT -->
## About The Project

A Django application to track and rate the media I consume: movies, TV shows, books, video games, music, and more.

> **Note:** This is a personal project, partly vibe-coded with the help of LLMs. It serves as a learning playground for Django, and to use as a personal tool.

## Features

- Track different media types (books, films, TV series, games, music, podcasts...)
- Rating system (1-10 scale)
- Markdown reviews
- Filters by type, status, year...

<p align="right">(<a href="#readme-top">back to top</a>)</p>

### Built With

- [![Django](https://img.shields.io/badge/Django-%23092E20.svg?logo=django&logoColor=white)](https://www.djangoproject.com/)
- [![DaisyUI](https://img.shields.io/badge/DaisyUI-5A0EF8?logo=daisyui&logoColor=fff)](https://daisyui.com/)
- [![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-%2338B2AC.svg?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
- [![HTMX](https://img.shields.io/badge/HTMX-36C?logo=htmx&logoColor=fff)](https://htmx.org/)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Docker Deployment

### Production Deployment (using pre-built image)

1. Download the Docker configuration files:
   ```bash
   mkdir -p docker
   cd docker
   curl -O https://raw.githubusercontent.com/PascalRepond/datakult/main/docker/docker-compose.prod.yml
   curl -O https://raw.githubusercontent.com/PascalRepond/datakult/main/docker/.env.example
   ```

2. Create your `.env` file from the example:
   ```bash
   cp .env.example .env
   ```

3. Edit the `.env` file and replace the placeholder values:
   - `SECRET_KEY`: Generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
   - `ALLOWED_HOSTS`: Add your domain and IP (e.g., `datakult.example.com,192.168.1.100,localhost`)
   - `DJANGO_SUPERUSER_PASSWORD`: Use a secure password

4. Start the application:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

The application will be available at `http://localhost:8000`. Your data will be stored in `docker/datakult_data/`.

Migrations and superuser creation are handled automatically on first start.

### Local Testing (build from source)

To test the Docker build locally before deploying:

```bash
# From the project root
docker compose -f docker/docker-compose.local.yml up --build
```

This builds the image from your current code. Default credentials are `admin/admin`.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Dev environment

### Prerequisites

Before you begin, make sure you have the following installed:

- **uv** (Python package manager)
  - Install with: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Node.js 20+** and npm 10+
  - Download from [nodejs.org](https://nodejs.org/)
  - Or use [nvm](https://github.com/nvm-sh/nvm): `nvm install 20 && nvm use`
- **gettext** (optional, for translations)
  - Debian/Ubuntu: `sudo apt-get install gettext`
  - macOS: `brew install gettext`

### Setup

```bash
# Clone the repository
git clone https://github.com/PascalRepond/datakult.git
cd datakult

# Install dependencies (using uv)
uv sync

# Initial setup (checks versions and installs everything)
uv run poe bootstrap

# Start the development server
uv run poe server
# The default superuser is admin/admin

```

### Available Commands

```bash
uv run poe server          # Dev server with Tailwind hot-reload
uv run poe migrate         # Apply migrations
uv run poe makemigrations  # Create migrations
uv run poe test            # Run tests
uv run poe lint            # Check code with Ruff
uv run poe format          # Format code
uv run poe ci              # Run all checks (format, lint, tests, audits)
```

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Backups

Datakult includes a backup system that exports both the database and media files into a `.tar.gz` archive.

### Manual Backup

**Local environment:**

```bash
# Create a backup
uv run poe backup

# Create a backup with automatic rotation (keep only 7 most recent)
uv run ./src/manage.py export_backup --keep=7

# Restore a backup
uv run poe restore path/to/backup.tar.gz
```

**Docker environment:**

```bash
# Create a backup
docker exec datakult uv run /app/src/manage.py export_backup

# Create a backup with automatic rotation (keep only 7 most recent)
docker exec datakult uv run /app/src/manage.py export_backup --keep=7

# Restore a backup
docker exec datakult uv run /app/src/manage.py import_backup /app/data/backups/backup.tar.gz
```

Backups are stored in:

- **Local:** `src/backups/`
- **Docker:** `/app/data/backups/` (mapped to `docker/datakult_data/backups/` on the host)

### Automated Backups

For production environments, it's recommended to configure automated backups using your system's cron scheduler:

**Example cron configuration (daily backup at 3 AM, keeping 7 most recent):**

```cron
0 3 * * * docker exec datakult uv run /app/src/manage.py export_backup --keep=7 >> /var/log/datakult-backup.log 2>&1
```

**Local development cron example:**

```cron
0 3 * * * cd /path/to/datakult && uv run ./src/manage.py export_backup --keep=7 >> /var/log/datakult-backup.log 2>&1
```

The `--keep` parameter automatically deletes old backups, maintaining only the N most recent backup files.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- LICENSE -->
## License

Distributed under the GNU GENERAL PUBLIC LICENSE. See `LICENSE` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
<!-- https://www.markdownguide.org/basic-syntax/#reference-style-links -->
[contributors-shield]: https://img.shields.io/github/contributors/PascalRepond/datakult.svg?style=for-the-badge
[contributors-url]: https://github.com/PascalRepond/datakult/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/PascalRepond/datakult.svg?style=for-the-badge
[forks-url]: https://github.com/PascalRepond/datakult/network/members
[stars-shield]: https://img.shields.io/github/stars/PascalRepond/datakult.svg?style=for-the-badge
[stars-url]: https://github.com/PascalRepond/datakult/stargazers
[issues-shield]: https://img.shields.io/github/issues/PascalRepond/datakult.svg?style=for-the-badge
[issues-url]: https://github.com/PascalRepond/datakult/issues
[license-shield]: https://img.shields.io/github/license/PascalRepond/datakult.svg?style=for-the-badge
[license-url]: https://github.com/PascalRepond/datakult/blob/main/LICENSE
