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

    def test_creates_backup_file(self, db):
        """A backup file is created."""
        with TemporaryDirectory() as tmpdir:
            backup_path = create_backup(output_dir=Path(tmpdir))

            assert backup_path.exists()
            assert backup_path.suffix == ".gz"
            assert backup_path.name.startswith("datakult_backup_")

    def test_backup_contains_metadata(self, db):
        """The backup contains a metadata.json file."""
        with TemporaryDirectory() as tmpdir:
            backup_path = create_backup(output_dir=Path(tmpdir))

            with tarfile.open(backup_path, "r:gz") as tar:
                assert "metadata.json" in tar.getnames()

                # Extract and verify metadata content
                metadata_file = tar.extractfile("metadata.json")
                metadata = json.loads(metadata_file.read())

                assert "created_at" in metadata
                assert "datakult_version" in metadata
                assert "django_version" in metadata
                assert "database_engine" in metadata

    def test_backup_contains_database(self, db):
        """The backup contains a database.json file."""
        with TemporaryDirectory() as tmpdir:
            backup_path = create_backup(output_dir=Path(tmpdir))

            with tarfile.open(backup_path, "r:gz") as tar:
                assert "database.json" in tar.getnames()

    def test_backup_includes_media_data(self, db):
        """The backup includes media data in the database dump."""
        # Create a media entry
        Media.objects.create(title="Test Media", media_type="BOOK")

        with TemporaryDirectory() as tmpdir:
            backup_path = create_backup(output_dir=Path(tmpdir))

            with tarfile.open(backup_path, "r:gz") as tar:
                db_file = tar.extractfile("database.json")
                db_data = json.loads(db_file.read())

                # Check that media data is present
                media_entries = [entry for entry in db_data if entry["model"] == "core.media"]
                assert len(media_entries) == 1
                assert media_entries[0]["fields"]["title"] == "Test Media"

    def test_custom_filename(self, db):
        """A custom filename can be provided."""
        with TemporaryDirectory() as tmpdir:
            backup_path = create_backup(output_dir=Path(tmpdir), filename="custom_backup.tar.gz")

            assert backup_path.name == "custom_backup.tar.gz"

    def test_custom_filename_adds_extension(self, db):
        """The .tar.gz extension is added if not present."""
        with TemporaryDirectory() as tmpdir:
            backup_path = create_backup(output_dir=Path(tmpdir), filename="custom")

            assert backup_path.name == "custom.tar.gz"

    def test_creates_output_directory(self, db):
        """The output directory is created if it doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "new_dir" / "backups"
            backup_path = create_backup(output_dir=output_dir)

            assert output_dir.exists()
            assert backup_path.exists()
