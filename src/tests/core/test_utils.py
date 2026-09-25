"""
Tests for core.utils module.

These tests verify the utility functions used by the application.
"""

import json
import tarfile

import pytest

from core.models import Agent, Media
from core.utils import create_backup, delete_orphan_agents_by_ids, get_datakult_version


def test_deletes_only_orphan_agents(media_factory):
    """Among the given agents, only those linked to no media are deleted."""
    orphan = Agent.objects.create(name="Orphan")
    active = Agent.objects.create(name="Active")
    media_factory(contributors=[active])

    deleted_count = delete_orphan_agents_by_ids([orphan.pk, active.pk])

    assert deleted_count == 1
    assert list(Agent.objects.values_list("name", flat=True)) == ["Active"]


@pytest.mark.parametrize(
    ("ids", "deleted"),
    [
        (lambda orphan: [], 0),
        (lambda orphan: [99999, 88888], 0),
        (lambda orphan: [None, orphan.pk, None], 1),
        (lambda orphan: [orphan.pk] * 3, 1),
    ],
    ids=["empty", "missing", "none values", "duplicates"],
)
def test_orphan_agents_are_counted_once(db, ids, deleted):
    """Missing and empty ids are skipped, and an orphan agent given several times is counted once."""
    orphan = Agent.objects.create(name="Orphan")

    assert delete_orphan_agents_by_ids(ids(orphan)) == deleted


@pytest.mark.parametrize(
    ("pyproject", "expected"), [('[project]\nversion = "1.2.3"\n', "1.2.3"), ("not = valid = toml", "unknown")]
)
def test_version_is_read_from_pyproject(settings, tmp_path, pyproject, expected):
    """The version is the one of pyproject.toml, or unknown when it cannot be parsed."""
    settings.BASE_DIR = tmp_path / "src"
    (tmp_path / "pyproject.toml").write_text(pyproject)

    assert get_datakult_version() == expected


def test_version_is_unknown_without_pyproject(settings, tmp_path):
    """Without pyproject.toml, the version is unknown."""
    settings.BASE_DIR = tmp_path / "src"

    assert get_datakult_version() == "unknown"


def test_creates_complete_backup(db, tmp_path):
    """A backup file is created with all expected content."""
    Media.objects.create(title="Test Media", media_type="BOOK")

    backup_path = create_backup(output_dir=tmp_path)

    assert backup_path.name.startswith("datakult_backup_")
    assert backup_path.name.endswith(".tar.gz")
    with tarfile.open(backup_path, "r:gz") as tar:
        metadata = json.loads(tar.extractfile("metadata.json").read())
        assert {"created_at", "datakult_version", "django_version", "database_engine"} <= metadata.keys()
        db_data = json.loads(tar.extractfile("database.json").read())
        media_entries = [entry for entry in db_data if entry["model"] == "core.media"]
        assert [entry["fields"]["title"] for entry in media_entries] == ["Test Media"]


@pytest.mark.parametrize("filename", ["custom", "custom.tar.gz"])
def test_backup_gets_a_custom_name_in_a_new_directory(db, tmp_path, filename):
    """A backup can be named, gets the .tar.gz extension if it lacks it, and creates its directory."""
    output_dir = tmp_path / "new_dir" / "backups"

    backup_path = create_backup(output_dir=output_dir, filename=filename)

    assert backup_path == output_dir / "custom.tar.gz"
    assert backup_path.exists()
