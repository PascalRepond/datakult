"""Import backup command."""

import json
import shutil
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """Import a complete backup of the Datakult application."""

    help = "Import a complete backup (database + media files) from a .tar.gz archive"

    def _validate_backup_file(self, backup_file: Path) -> None:
        """Validate the backup file exists and has correct format."""
        if not backup_file.exists():
            msg = f"Backup file not found: {backup_file}"
            raise CommandError(msg)

        if not str(backup_file).endswith(".tar.gz"):
            msg = f"Invalid backup file format. Expected .tar.gz, got: {backup_file}"
            raise CommandError(msg)

    def _extract_backup(self, backup_file: Path, temp_path: Path) -> None:
        """Extract the backup archive with security checks."""
        self.stdout.write("Extracting backup archive...")
        with tarfile.open(backup_file, "r:gz") as tar:
            # Security check: ensure all paths are safe
            for member in tar.getmembers():
                member_path = Path(member.name)
                if member_path.is_absolute() or ".." in member_path.parts:
                    msg = f"Unsafe path in archive: {member.name}"
                    raise CommandError(msg)
            # Use filter for safe extraction (Python 3.12+) or manual extraction
            tar.extractall(temp_path, filter="data")

    def _import_database(self, temp_path: Path, *, flush: bool) -> None:
        """Import the database from the backup."""
        if flush:
            self.stdout.write("Flushing existing database...")
            call_command("flush", interactive=False, verbosity=0)

        database_file = temp_path / "database.json"
        if not database_file.exists():
            msg = "database.json not found in backup archive"
            raise CommandError(msg)

        self.stdout.write("Importing database...")
        call_command("loaddata", str(database_file), verbosity=1)

    def _import_media(self, temp_path: Path) -> None:
        """Import media files from the backup."""
        media_backup = temp_path / "media"
        if media_backup.exists():
            self.stdout.write("Importing media files...")
            media_root = Path(settings.MEDIA_ROOT)
            media_root.mkdir(parents=True, exist_ok=True)

            # Copy all files from backup to media root
            for item in media_backup.rglob("*"):
                if item.is_file():
                    relative_path = item.relative_to(media_backup)
                    dest_path = media_root / relative_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_path)

            self.stdout.write(f"Media files copied to {media_root}")
        else:
            self.stdout.write(self.style.WARNING("No media files found in backup"))

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "backup_file",
            type=str,
            help="Path to the backup file (.tar.gz) to import",
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Flush the database before importing (removes all existing data)",
        )
        parser.add_argument(
            "--no-media",
            action="store_true",
            help="Skip importing media files (only import database)",
        )

    def handle(self, **options):
        """Execute the backup import."""
        backup_file = Path(options["backup_file"])

        # Validate backup file
        self._validate_backup_file(backup_file)

        self.stdout.write(f"Importing backup from: {backup_file}")

        # Warning about data replacement
        if options["flush"]:
            self.stdout.write(
                self.style.WARNING("⚠ WARNING: --flush option will DELETE ALL EXISTING DATA before importing!")
            )
        else:
            self.stdout.write(
                self.style.WARNING("⚠ WARNING: This will merge/update data. Use --flush to completely replace.")
            )

        # Create a temporary directory for extraction
        with TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            try:
                # Step 1: Extract the archive
                self._extract_backup(backup_file, temp_path)

                # Step 2: Read and display metadata
                metadata_file = temp_path / "metadata.json"
                if metadata_file.exists():
                    with metadata_file.open() as f:
                        metadata = json.load(f)
                    self.stdout.write(f"Backup created at: {metadata.get('created_at', 'unknown')}")

                # Step 3: Import database
                self._import_database(temp_path, flush=options["flush"])

                # Step 4: Import media files
                if not options["no_media"]:
                    self._import_media(temp_path)
                else:
                    self.stdout.write("Skipping media files import (--no-media)")

                self.stdout.write(self.style.SUCCESS("✓ Backup imported successfully!"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Import failed: {e!s}"))
                raise
