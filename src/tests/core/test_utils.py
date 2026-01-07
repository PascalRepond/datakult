"""
Tests for core.utils module.

These tests verify the utility functions used by the application.
"""

import json
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory

from core.models import Agent, Media
from core.utils import create_backup, delete_orphan_agents_by_ids, get_datakult_version


class TestDeleteOrphanAgentsByIds:
    """Tests for the delete_orphan_agents_by_ids function."""

    def test_deletes_orphan_agent(self, db):
        """An agent with no media is deleted."""
        orphan = Agent.objects.create(name="Orphan Agent")
        orphan_id = orphan.pk

        deleted_count = delete_orphan_agents_by_ids([orphan_id])

        assert deleted_count == 1
        assert not Agent.objects.filter(pk=orphan_id).exists()

    def test_keeps_agent_with_media(self, db):
        """An agent linked to a media is not deleted."""
        agent = Agent.objects.create(name="Active Agent")
        media = Media.objects.create(title="Test Media", media_type="BOOK")
        media.contributors.add(agent)

        deleted_count = delete_orphan_agents_by_ids([agent.pk])

        assert deleted_count == 0
        assert Agent.objects.filter(pk=agent.pk).exists()

    def test_mixed_agents(self, db):
        """Only orphan agents are deleted from a mixed list."""
        orphan = Agent.objects.create(name="Orphan")
        active = Agent.objects.create(name="Active")
        media = Media.objects.create(title="Test Media", media_type="BOOK")
        media.contributors.add(active)

        deleted_count = delete_orphan_agents_by_ids([orphan.pk, active.pk])

        assert deleted_count == 1
        assert not Agent.objects.filter(pk=orphan.pk).exists()
        assert Agent.objects.filter(pk=active.pk).exists()

    def test_empty_list(self, db):
        """Returns 0 when given an empty list."""
        deleted_count = delete_orphan_agents_by_ids([])

        assert deleted_count == 0

    def test_nonexistent_ids(self, db):
        """Handles non-existent IDs gracefully."""
        deleted_count = delete_orphan_agents_by_ids([99999, 88888])

        assert deleted_count == 0

    def test_handles_none_values(self, db):
        """None values in the list are filtered out."""
        orphan = Agent.objects.create(name="Orphan")

        deleted_count = delete_orphan_agents_by_ids([None, orphan.pk, None])

        assert deleted_count == 1

    def test_handles_duplicate_ids(self, db):
        """Duplicate IDs are handled correctly."""
        orphan = Agent.objects.create(name="Orphan")

        deleted_count = delete_orphan_agents_by_ids([orphan.pk, orphan.pk, orphan.pk])

        assert deleted_count == 1


class TestGetDatakultVersion:
    """Tests for the get_datakult_version function."""

    def test_returns_version_string(self):
        """The function returns a version string."""
        version = get_datakult_version()

        assert isinstance(version, str)
        assert version != ""

    def test_version_format_or_unknown(self):
        """The version is either in semver format or 'unknown'."""
        version = get_datakult_version()

        # Should be either a version number (e.g., "0.1.0") or "unknown"
        assert version == "unknown" or version[0].isdigit()


class TestCreateBackup:
    """Tests for the create_backup function."""

    def test_creates_complete_backup(self, db):
        """A backup file is created with all expected content."""
        # Create a media entry to verify data backup
        Media.objects.create(title="Test Media", media_type="BOOK")

        with TemporaryDirectory() as tmpdir:
            backup_path = create_backup(output_dir=Path(tmpdir))

            # Verify file creation
            assert backup_path.exists()
            assert backup_path.suffix == ".gz"
            assert backup_path.name.startswith("datakult_backup_")

            # Verify archive contents
            with tarfile.open(backup_path, "r:gz") as tar:
                # Check metadata.json exists and has correct structure
                assert "metadata.json" in tar.getnames()
                metadata_file = tar.extractfile("metadata.json")
                metadata = json.loads(metadata_file.read())
                assert "created_at" in metadata
                assert "datakult_version" in metadata
                assert "django_version" in metadata
                assert "database_engine" in metadata

                # Check database.json exists and contains media data
                assert "database.json" in tar.getnames()
                db_file = tar.extractfile("database.json")
                db_data = json.loads(db_file.read())
                media_entries = [entry for entry in db_data if entry["model"] == "core.media"]
                assert len(media_entries) == 1
                assert media_entries[0]["fields"]["title"] == "Test Media"

    def test_custom_filename_with_extension_handling(self, db):
        """Custom filenames work correctly with automatic .tar.gz extension."""
        with TemporaryDirectory() as tmpdir:
            # Test with full extension
            backup_path1 = create_backup(output_dir=Path(tmpdir), filename="custom_backup.tar.gz")
            assert backup_path1.name == "custom_backup.tar.gz"

            # Test without extension - should be added automatically
            backup_path2 = create_backup(output_dir=Path(tmpdir), filename="custom")
            assert backup_path2.name == "custom.tar.gz"

    def test_creates_output_directory(self, db):
        """The output directory is created if it doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "new_dir" / "backups"
            backup_path = create_backup(output_dir=output_dir)

            assert output_dir.exists()
            assert backup_path.exists()
