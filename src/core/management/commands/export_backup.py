"""Export backup command."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.utils import create_backup


class Command(BaseCommand):
    """Export a complete backup of the Datakult application."""

    help = "Export a complete backup (database + media files) as a .tar.gz archive"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--output",
            type=str,
            help="Output directory for the backup file (default: /app/data/backups or ./backups)",
        )
        parser.add_argument(
            "--filename",
            type=str,
            help="Custom filename for the backup (default: datakult_backup_YYYYMMDD_HHMMSS.tar.gz)",
        )
        parser.add_argument(
            "--keep",
            type=int,
            default=None,
            help="Number (>=1) of backups to keep (optional). If specified, old backups will be automatically deleted.",
        )

    def handle(self, **options):
        """Execute the backup export."""
        output_dir = Path(options["output"]) if options["output"] else None
        filename = options["filename"]
        keep_count = options["keep"]

        self.stdout.write("Creating backup…")

        try:
            backup_path = create_backup(output_dir=output_dir, filename=filename)
            file_size_mb = backup_path.stat().st_size / (1024 * 1024)

            self.stdout.write(
                self.style.SUCCESS(f"✓ Backup created successfully: {backup_path} ({file_size_mb:.2f} MB)")
            )

            # Rotate old backups if --keep is specified
            if keep_count is not None:
                if keep_count < 1:
                    msg = "--keep must be at least 1"
                    raise CommandError(msg)  # noqa: TRY301
                self._rotate_backups(backup_path.parent, keep_count)

            return str(backup_path)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Backup failed: {e!s}"))
            raise

    def _rotate_backups(self, backup_dir: Path, keep_count: int):
        """Delete old backups, keeping only the N most recent ones."""
        # Find all backup files in the directory
        # Sort by modification time for robustness
        backup_files = sorted(
            backup_dir.glob("datakult_backup_*.tar.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,  # Most recent first
        )

        # Delete old backups if we have more than keep_count
        if len(backup_files) > keep_count:
            files_to_delete = backup_files[keep_count:]
            self.stdout.write(f"Found {len(backup_files)} backups, keeping {keep_count} most recent…")

            for old_backup in files_to_delete:
                self.stdout.write(f"Deleting old backup: {old_backup.name}")
                old_backup.unlink()

            self.stdout.write(self.style.SUCCESS(f"✓ Deleted {len(files_to_delete)} old backup(s)"))
        else:
            self.stdout.write(f"Found {len(backup_files)} backup(s), no rotation needed (keeping {keep_count})")
