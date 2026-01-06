"""Export backup command."""

from pathlib import Path

from django.core.management.base import BaseCommand

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

    def handle(self, **options):
        """Execute the backup export."""
        output_dir = Path(options["output"]) if options["output"] else None
        filename = options["filename"]

        self.stdout.write("Creating backup…")

        try:
            backup_path = create_backup(output_dir=output_dir, filename=filename)
            file_size_mb = backup_path.stat().st_size / (1024 * 1024)

            self.stdout.write(
                self.style.SUCCESS(f"✓ Backup created successfully: {backup_path} ({file_size_mb:.2f} MB)")
            )

            return str(backup_path)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Backup failed: {e!s}"))
            raise
