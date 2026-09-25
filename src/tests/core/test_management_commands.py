"""
Tests for core management commands.

These tests verify the backup-related management commands.
"""

import json
import tarfile
from io import BytesIO, StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.models import Media, SavedView
from core.utils import create_backup


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
    with tarfile.open(old_backup, "w:gz") as tar:
        for name, content in members.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(info, BytesIO(content))

    call_command("import_backup", str(old_backup), "--flush", "--no-media", stdout=StringIO())

    assert SavedView.objects.filter(name="Old view").exists()
