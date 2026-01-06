"""Auto backup command with rotation."""

from pathlib import Path

from django.core.management.base import BaseCommand

from core.utils import create_backup


class Command(BaseCommand):
    """Create a backup and rotate old backups."""

    help = "Create a backup and keep only the N most recent backups (default: 7)"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "--keep",
            type=int,
            default=7,
            help="Number of backups to keep (default: 7)",
        )
        parser.add_argument(
            "--output",
            type=str,
            help="Output directory for backups (default: auto-detected)",
        )

    def handle(self, **options):
        """Execute the automatic backup with rotation."""
        keep_count = options["keep"]
        output_dir = Path(options["output"]) if options["output"] else None

        try:
            # Create the backup
            self.stdout.write("Creating backup…")
            backup_path = create_backup(output_dir=output_dir)
            self.stdout.write(self.style.SUCCESS(f"✓ Backup created: {backup_path}"))

            # Get the backup directory
            backup_dir = backup_path.parent

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

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"✗ Automatic backup failed: {e!s}"))
            raise
