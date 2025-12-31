import json
import tarfile
import tomllib
from collections.abc import Iterable
from io import BytesIO, StringIO
from pathlib import Path

import django
from django.conf import settings
from django.core.management import call_command
from django.db.models import Count
from django.utils import timezone

from .models import Agent


def get_datakult_version() -> str:
    """Get the Datakult version from pyproject.toml.

    Returns:
        Version string (e.g., "0.1.0") or "unknown" if unable to read
    """
    pyproject_path = Path(settings.BASE_DIR).parent / "pyproject.toml"
    try:
        with pyproject_path.open("rb") as f:
            pyproject_data = tomllib.load(f)
        return pyproject_data.get("project", {}).get("version", "unknown")
    except (FileNotFoundError, KeyError, tomllib.TOMLDecodeError):
        return "unknown"


def delete_orphan_agents_by_ids(agent_ids: Iterable[int]) -> int:
    """Delete all Agents in the given IDs that are not linked to any Media.

    Returns the number of Agents deleted.
    """
    ids = list({int(i) for i in agent_ids if i is not None})
    if not ids:
        return 0
    qs = Agent.objects.filter(pk__in=ids).annotate(n=Count("media")).filter(n=0)
    count = qs.count()
    qs.delete()
    return count


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
        data_dir = Path(settings.BASE_DIR).parent / "data"
        output_dir = data_dir / "backups" if data_dir.exists() else Path(settings.BASE_DIR) / "backups"

    # Create backup directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename with timestamp (including microseconds to avoid collisions)
    if filename is None:
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S_%f")
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
    json_data = json_output.getvalue()

    # Step 2: Create the tar.gz archive
    with tarfile.open(backup_path, "w:gz") as tar:
        # Add metadata file
        metadata = {
            "created_at": timezone.now().isoformat(),
            "datakult_version": get_datakult_version(),
            "django_version": django.get_version(),
            "database_engine": settings.DATABASES["default"]["ENGINE"],
        }
        metadata_json = json.dumps(metadata, indent=2)
        metadata_bytes = metadata_json.encode("utf-8")
        metadata_info = tarfile.TarInfo(name="metadata.json")
        metadata_info.size = len(metadata_bytes)
        tar.addfile(metadata_info, fileobj=BytesIO(metadata_bytes))

        # Add database dump
        db_bytes = json_data.encode("utf-8")
        db_info = tarfile.TarInfo(name="database.json")
        db_info.size = len(db_bytes)
        tar.addfile(db_info, fileobj=BytesIO(db_bytes))

        # Add media files if they exist
        media_root = Path(settings.MEDIA_ROOT)
        if media_root.exists() and any(media_root.iterdir()):
            tar.add(media_root, arcname="media", recursive=True)

    return backup_path
