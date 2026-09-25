"""
Tests for core management commands.

These tests verify the backup-related management commands.
"""

import json
import tarfile
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.models import Media, SavedView
from core.utils import create_backup
from tests.helpers import archive_bytes


def test_export_writes_the_backup_where_asked(db, tmp_path):
    """The export_backup command writes the backup with the given name and directory, and reports it."""
    out = StringIO()

    result = call_command("export_backup", f"--output={tmp_path}", "--filename=my_backup.tar.gz", stdout=out)

    assert Path(result) == tmp_path / "my_backup.tar.gz"
    assert Path(result).exists()
    assert "Backup created successfully" in out.getvalue()


@pytest.mark.parametrize(("options", "remaining"), [(["--keep=2"], 2), ([], 4)])
def test_export_keeps_the_latest_backups(db, tmp_path, options, remaining):
    """With --keep, only the latest backups are kept; without it, none is deleted."""
    for _ in range(4):
        latest = call_command("export_backup", f"--output={tmp_path}", *options, stdout=StringIO())

    assert len(list(tmp_path.glob("datakult_backup_*.tar.gz"))) == remaining
    assert Path(latest).exists()


def test_export_refuses_to_keep_no_backup(db, tmp_path):
    """--keep must keep at least one backup, which is checked before any backup is written."""
    with pytest.raises(CommandError, match="--keep must be at least 1"):
        call_command("export_backup", f"--output={tmp_path}", "--keep=0", stdout=StringIO())

    assert list(tmp_path.glob("*.tar.gz")) == []


def test_import_rejects_a_missing_file(db, tmp_path):
    """The import_backup command rejects a file that does not exist."""
    with pytest.raises(CommandError, match="Backup file not found"):
        call_command("import_backup", str(tmp_path / "missing.tar.gz"))


def test_import_rejects_a_file_that_is_not_an_archive(db, tmp_path):
    """The import_backup command rejects a file that is not a .tar.gz archive."""
    path = tmp_path / "backup.txt"
    path.write_text("not a backup")

    with pytest.raises(CommandError, match="Invalid backup file format"):
        call_command("import_backup", str(path))


@pytest.mark.parametrize(("options", "files_restored"), [([], True), (["--no-media"], False)])
def test_import_restores_the_backup(media_factory, settings, tmp_path, options, files_restored):
    """The import_backup command restores the media of a backup, and its media files unless told otherwise."""
    media_factory(title="Original", status="COMPLETED")
    cover = settings.MEDIA_ROOT / "covers" / "cover.jpg"
    cover.parent.mkdir(parents=True)
    cover.write_bytes(b"cover")
    backup_path = create_backup(output_dir=tmp_path / "backups")
    Media.objects.all().delete()
    cover.unlink()
    out = StringIO()

    call_command("import_backup", str(backup_path), *options, stdout=out)

    assert list(Media.objects.values_list("title", "status")) == [("Original", "COMPLETED")]
    assert cover.exists() is files_restored
    assert ("Skipping media files import" in out.getvalue()) is not files_restored


def test_import_with_flush_replaces_data(media_factory, tmp_path):
    """The import_backup command with --flush replaces all data."""
    media_factory(title="Original")
    backup_path = create_backup(output_dir=tmp_path)
    media_factory(title="New Media", media_type="FILM")

    call_command("import_backup", str(backup_path), "--flush", stdout=StringIO())

    assert list(Media.objects.values_list("title", flat=True)) == ["Original"]


@pytest.mark.parametrize(
    ("members", "error"),
    [({"metadata.json": b"{}"}, "database.json not found"), ({"database.json": b"not json"}, "Invalid database.json")],
    ids=["no database", "invalid database"],
)
def test_failed_import_with_flush_keeps_the_data(media, tmp_path, members, error):
    """An import that fails says why, and leaves the data as it was, even when it was to flush it first."""
    archive = tmp_path / "broken.tar.gz"
    archive.write_bytes(archive_bytes(members))

    with pytest.raises(CommandError, match=error):
        call_command("import_backup", str(archive), "--flush", stdout=StringIO())

    assert list(Media.objects.values_list("title", flat=True)) == ["Test Media"]


def test_import_restores_backup_with_removed_fields(saved_view_factory, tmp_path):
    """A backup made before a field was removed from a model still restores."""
    saved_view_factory(name="Old view")
    backup_path = create_backup(output_dir=tmp_path)
    # Simulate an older backup, whose saved views still had a view_mode field
    with tarfile.open(backup_path, "r:gz") as tar:
        members = {member.name: tar.extractfile(member).read() for member in tar.getmembers() if member.isfile()}
    database = json.loads(members["database.json"])
    for obj in database:
        if obj["model"] == "core.savedview":
            obj["fields"]["view_mode"] = "list"
    members["database.json"] = json.dumps(database).encode()
    old_backup = tmp_path / "old_backup.tar.gz"
    old_backup.write_bytes(archive_bytes(members))

    call_command("import_backup", str(old_backup), "--flush", "--no-media", stdout=StringIO())

    assert SavedView.objects.filter(name="Old view").exists()
