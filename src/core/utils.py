import json
import tarfile
import tomllib
from io import BytesIO, StringIO
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

import django
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from .models import Agent


def get_datakult_version() -> str:
    """Get the Datakult version from pyproject.toml.

    Returns:
        Version string (e.g., "0.1.0") or "unknown" if unable to read
    """
    try:
        with (settings.BASE_DIR.parent / "pyproject.toml").open("rb") as f:
            pyproject_data = tomllib.load(f)
    except FileNotFoundError, tomllib.TOMLDecodeError:
        return "unknown"
    return pyproject_data.get("project", {}).get("version", "unknown")


def delete_orphan_agents_by_ids(agent_ids: Iterable[int]) -> int:
    """Delete all Agents in the given IDs that are not linked to any Media.

    Returns the number of Agents deleted.
    """
    ids = list({int(i) for i in agent_ids if i is not None})
    if not ids:
        return 0
    deleted, _per_model = Agent.objects.filter(pk__in=ids, media__isnull=True).delete()
    return deleted


def _add_bytes(tar, name: str, data: bytes) -> None:
    """Add a file of the given name, holding `data`, to a tar archive."""
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    tar.addfile(info, fileobj=BytesIO(data))


def create_backup(output_dir: Path | None = None, filename: str | None = None) -> Path:
    """
    Create a complete backup of the Datakult application.

    This function creates a compressed archive (.tar.gz) containing:
    - JSON dump of all database data
    - All media files (cover images, etc.)

    Args:
        output_dir: Directory where to save the backup (default: auto-detected)
        filename: Custom filename for the backup (default: datakult_backup_YYYYMMDD_HHMMSS_microseconds.tar.gz)

    Returns:
        Path to the created backup file

    Raises:
        Exception: If backup creation fails
    """
    # Determine output directory
    if output_dir is None:
        # Default: use /app/data/backups in Docker, or ./backups locally
        data_dir = settings.BASE_DIR.parent / "data"
        output_dir = data_dir / "backups" if data_dir.exists() else settings.BASE_DIR / "backups"

    # Create backup directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp (including microseconds to avoid collisions)
    now = timezone.now()
    if filename is None:
        timestamp = now.strftime("%Y%m%d_%H%M%S_%f")
        filename = f"datakult_backup_{timestamp}.tar.gz"
    elif not filename.endswith(".tar.gz"):
        filename += ".tar.gz"

    backup_path = output_dir / filename

    # Step 1: Export database to JSON
    json_output = StringIO()
    call_command(
        "dumpdata",
        exclude=["contenttypes", "auth.permission", "sessions.session"],
        indent=2,
        stdout=json_output,
    )
    metadata = {
        "created_at": now.isoformat(),
        "datakult_version": get_datakult_version(),
        "django_version": django.get_version(),
        "database_engine": settings.DATABASES["default"]["ENGINE"],
    }

    # Step 2: Create the tar.gz archive
    with tarfile.open(backup_path, "w:gz") as tar:
        _add_bytes(tar, "metadata.json", json.dumps(metadata, indent=2).encode())
        _add_bytes(tar, "database.json", json_output.getvalue().encode())

        # Add media files if they exist
        media_root = Path(settings.MEDIA_ROOT)
        if media_root.exists() and any(media_root.iterdir()):
            tar.add(media_root, arcname="media", recursive=True)

    return backup_path
