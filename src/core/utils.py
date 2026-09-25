import json
import tarfile
import tomllib
from io import BytesIO, StringIO
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import BinaryIO

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


def backup_filename() -> str:
    """Return the default name of a backup, timestamped to the microsecond to avoid collisions."""
    return f"datakult_backup_{timezone.now():%Y%m%d_%H%M%S_%f}.tar.gz"


def write_backup(fileobj: BinaryIO) -> None:
    """
    Write a complete backup of the Datakult application to a binary file, as a compressed archive (.tar.gz).

    The archive holds the metadata of the backup, a JSON dump of all database data and all media files.
    """
    json_output = StringIO()
    call_command(
        "dumpdata",
        exclude=["contenttypes", "auth.permission", "sessions.session"],
        indent=2,
        stdout=json_output,
    )
    metadata = {
        "created_at": timezone.now().isoformat(),
        "datakult_version": get_datakult_version(),
        "django_version": django.get_version(),
        "database_engine": settings.DATABASES["default"]["ENGINE"],
    }

    with tarfile.open(fileobj=fileobj, mode="w:gz") as tar:
        _add_bytes(tar, "metadata.json", json.dumps(metadata, indent=2).encode())
        _add_bytes(tar, "database.json", json_output.getvalue().encode())

        # Add media files if they exist
        media_root = Path(settings.MEDIA_ROOT)
        if media_root.exists() and any(media_root.iterdir()):
            tar.add(media_root, arcname="media", recursive=True)


def create_backup(output_dir: Path | None = None, filename: str | None = None) -> Path:
    """
    Create a file holding a complete backup of the Datakult application, as written by `write_backup`.

    Args:
        output_dir: Directory where to save the backup (default: auto-detected)
        filename: Custom filename for the backup (default: given by `backup_filename`)

    Returns:
        Path to the created backup file
    """
    if output_dir is None:
        # Default: use /app/data/backups in Docker, or ./backups locally
        data_dir = settings.BASE_DIR.parent / "data"
        output_dir = data_dir / "backups" if data_dir.exists() else settings.BASE_DIR / "backups"
    output_dir.mkdir(parents=True, exist_ok=True)

    if filename is None:
        filename = backup_filename()
    elif not filename.endswith(".tar.gz"):
        filename += ".tar.gz"

    backup_path = output_dir / filename
    try:
        with backup_path.open("wb") as fileobj:
            write_backup(fileobj)
    except Exception:
        # A partial backup would pass for a complete one, and could have older backups rotated out
        backup_path.unlink(missing_ok=True)
        raise
    return backup_path
