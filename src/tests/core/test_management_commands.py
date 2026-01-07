"""
Tests for core management commands.

These tests verify the backup-related management commands.
"""

import json
import tarfile
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.models import Media


class TestExportBackupCommand:
    """Tests for the export_backup management command."""

    def test_export_creates_backup(self, db):
        """The export_backup command creates a backup file."""
        with TemporaryDirectory() as tmpdir:
            out = StringIO()
            result = call_command("export_backup", f"--output={tmpdir}", stdout=out)

            # The command should return the path to the backup
            assert result is not None
            backup_path = Path(result)
            assert backup_path.exists()
            assert backup_path.name.startswith("datakult_backup_")

    def test_export_with_custom_filename(self, db):
        """The export_backup command accepts a custom filename."""
        with TemporaryDirectory() as tmpdir:
            out = StringIO()
            result = call_command(
                "export_backup",
                f"--output={tmpdir}",
                "--filename=my_backup.tar.gz",
                stdout=out,
            )

            backup_path = Path(result)
            assert backup_path.name == "my_backup.tar.gz"

    def test_export_displays_success_message(self, db):
        """The command displays a success message."""
        with TemporaryDirectory() as tmpdir:
            out = StringIO()
            call_command("export_backup", f"--output={tmpdir}", stdout=out)

            output = out.getvalue()
            assert "Backup created successfully" in output

    def test_export_includes_media_data(self, db):
        """The exported backup includes media data."""
        Media.objects.create(title="Test Media", media_type="BOOK")

        with TemporaryDirectory() as tmpdir:
            out = StringIO()
            result = call_command("export_backup", f"--output={tmpdir}", stdout=out)

            backup_path = Path(result)
            with tarfile.open(backup_path, "r:gz") as tar:
                db_file = tar.extractfile("database.json")
                db_data = json.loads(db_file.read())

                media_entries = [entry for entry in db_data if entry["model"] == "core.media"]
                assert len(media_entries) == 1

    def test_export_with_keep_rotates_old_backups(self, db):
        """The export_backup command with --keep rotates backups correctly."""
        with TemporaryDirectory() as tmpdir:
            # Create 4 backups with keep=2
            for _ in range(4):
                out = StringIO()
                call_command("export_backup", f"--output={tmpdir}", "--keep=2", stdout=out)

            # Only 2 most recent should remain
            backups = sorted(
                Path(tmpdir).glob("datakult_backup_*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            assert len(backups) == 2

            # Check that rotation message was displayed
            output = out.getvalue()
            assert "Deleting old backup" in output or "Deleted" in output

    def test_export_without_keep_no_rotation(self, db):
        """The export_backup command without --keep doesn't delete old backups."""
        with TemporaryDirectory() as tmpdir:
            # Create 3 backups without specifying --keep
            for _ in range(3):
                out = StringIO()
                call_command("export_backup", f"--output={tmpdir}", stdout=out)

            # All 3 should remain
            backups = list(Path(tmpdir).glob("datakult_backup_*.tar.gz"))
            assert len(backups) == 3


class TestImportBackupCommand:
    """Tests for the import_backup management command."""

    def test_import_requires_file_argument(self, db):
        """The import_backup command requires a backup file argument."""
        with pytest.raises(CommandError, match="the following arguments are required"):
            call_command("import_backup")

    def test_import_rejects_nonexistent_file(self, db):
        """The import_backup command rejects a non-existent file."""
        with pytest.raises(CommandError, match="Backup file not found"):
            call_command("import_backup", "/nonexistent/backup.tar.gz")

    def test_import_rejects_invalid_format(self, db):
        """The import_backup command rejects files with invalid format."""
        with TemporaryDirectory() as tmpdir:
            # Create a non-.tar.gz file
            invalid_file = Path(tmpdir) / "backup.txt"
            invalid_file.write_text("not a backup")

            with pytest.raises(CommandError, match="Invalid backup file format"):
                call_command("import_backup", str(invalid_file))

    def test_import_restores_media_data(self, db):
        """The import_backup command restores media data."""
        # Create a media entry and backup
        original_media = Media.objects.create(title="Original Media", media_type="BOOK", status="COMPLETED")

        with TemporaryDirectory() as tmpdir:
            # Create a backup
            out = StringIO()
            backup_path = Path(call_command("export_backup", f"--output={tmpdir}", stdout=out))

            # Clear the database
            Media.objects.all().delete()
            assert Media.objects.count() == 0

            # Import the backup without --flush (merge mode)
            call_command("import_backup", str(backup_path))

            # Verify the media is restored
            assert Media.objects.count() == 1
            restored_media = Media.objects.first()
            assert restored_media.title == original_media.title
            assert restored_media.status == original_media.status

    def test_import_with_flush_replaces_data(self, db):
        """The import_backup command with --flush replaces all data."""
        # Create initial media and backup
        Media.objects.create(title="Original", media_type="BOOK")

        with TemporaryDirectory() as tmpdir:
            # Create a backup
            out = StringIO()
            backup_path = Path(call_command("export_backup", f"--output={tmpdir}", stdout=out))

            # Add new media (not in backup)
            Media.objects.create(title="New Media", media_type="FILM")
            assert Media.objects.count() == 2

            # Import with --flush should remove "New Media"
            call_command("import_backup", str(backup_path), "--flush")

            # Only the original media should remain
            assert Media.objects.count() == 1
            assert Media.objects.first().title == "Original"

    def test_import_with_no_media_flag(self, db):
        """The import_backup command with --no-media skips media files."""
        Media.objects.create(title="Test", media_type="BOOK")

        with TemporaryDirectory() as tmpdir:
            # Create a backup
            out = StringIO()
            backup_path = Path(call_command("export_backup", f"--output={tmpdir}", stdout=out))

            # Clear database
            Media.objects.all().delete()

            # Import without media files
            out = StringIO()
            call_command("import_backup", str(backup_path), "--no-media", stdout=out)

            # Database should be restored
            assert Media.objects.count() == 1

            # Check output mentions skipping media
            output = out.getvalue()
            assert "Skipping media files import" in output
