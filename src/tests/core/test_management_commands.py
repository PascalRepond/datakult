"""
Tests for core management commands.

These tests verify the backup and page count management commands.
"""

import json
import tarfile
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from core.models import Media, SavedView
from core.services.base import APIError
from core.services.googlebooks import GoogleBooksResult
from core.services.openlibrary import OpenLibraryResult
from core.utils import create_backup
from tests.helpers import archive_bytes

FILL_PAGE_COUNTS = "core.management.commands.fill_page_counts"


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


def _work(title, page_count):
    return OpenLibraryResult(
        work_key="/works/OL1W", title=title, authors=[], year=None, cover_id=None, page_count=page_count
    )


@pytest.fixture
def page_count_sources(monkeypatch):
    """Replace the OpenLibrary and Google Books clients of fill_page_counts by mocks, returned in that order, finding
    nothing until told otherwise, and remove the delay between media."""
    openlibrary, googlebooks = MagicMock(), MagicMock()
    openlibrary.search_books.return_value = googlebooks.search_books.return_value = []
    monkeypatch.setattr(f"{FILL_PAGE_COUNTS}.get_openlibrary_client", lambda: openlibrary)
    monkeypatch.setattr(f"{FILL_PAGE_COUNTS}.get_googlebooks_client", lambda: googlebooks)
    monkeypatch.setattr(f"{FILL_PAGE_COUNTS}.REQUEST_DELAY", 0)
    return openlibrary, googlebooks


def test_fill_page_counts_asks_the_source_of_the_link_or_searches_the_title(media_factory, agent, page_count_sources):
    """A linked work or volume is asked for its page count first; then media are searched by title, series and
    subtitle left out, and author surname, on OpenLibrary, whose first result with a page count is taken, then on
    Google Books.
    """
    openlibrary, googlebooks = page_count_sources
    openlibrary.search_books.side_effect = lambda query, limit: {
        "key:/works/OL1W": [_work("Dune", 412)],
        "key:/works/OL2W": [_work("Anathem", None)],
        'title:"Anathem"': [_work("Anathem", 937)],
        'title:"Foundation" author:"Author"': [_work("Foundation", None), _work("Foundation", 255)],
    }.get(query, [])
    googlebooks.search_books.side_effect = lambda query, limit: {
        'intitle:"Watchmen" inauthor:"Author"': [
            GoogleBooksResult(volume_id="vol2", title="Watchmen", authors=[], year=None, thumbnail_url=None)
        ],
    }.get(query, [])
    googlebooks.get_volume_details.side_effect = lambda volume_id: {
        "vol1": {"title": "Neuromancer", "page_count": 271},
        "vol2": {"title": "Watchmen", "page_count": 416},
    }[volume_id]
    media_factory(title="Dune", external_uri="https://openlibrary.org/works/OL1W/Dune")
    media_factory(title="Anathem", external_uri="https://openlibrary.org/works/OL2W")
    media_factory(title="Neuromancer", external_uri="https://play.google.com/store/books/details?id=vol1")
    media_factory(title="Foundation (Foundation #1)", contributors=[agent])
    media_factory(title="Watchmen: Deluxe", media_type="COMIC", contributors=[agent])

    call_command("fill_page_counts", stdout=StringIO())

    assert dict(Media.objects.values_list("title", "page_count")) == {
        "Dune": 412,
        "Anathem": 937,
        "Neuromancer": 271,
        "Foundation (Foundation #1)": 255,
        "Watchmen: Deluxe": 416,
    }


@pytest.mark.parametrize(("options", "saved"), [([], 412), (["--dry-run"], None)])
def test_fill_page_counts_lists_what_it_found_or_not(media_factory, page_count_sources, options, saved):
    """The page counts found are listed, and saved without marking their media as updated unless it is a dry run,
    and the media without page count found are listed to be filled in by hand."""
    openlibrary, _googlebooks = page_count_sources
    openlibrary.search_books.side_effect = lambda query, limit: [_work("Dune", 412)] if "Dune" in query else []
    dune = media_factory(title="Dune")
    media_factory(title="Unknown")
    out = StringIO()

    call_command("fill_page_counts", *options, stdout=out)

    dune_after = Media.objects.get(pk=dune.pk)
    assert (dune_after.page_count, dune_after.updated_at) == (saved, dune.updated_at)
    assert "Dune: 412 pages, found as Dune" in out.getvalue()
    assert "No page count found for 1 media, to fill in by hand:\n  Unknown" in out.getvalue()


def test_fill_page_counts_only_asks_google_books_for_the_volume_of_its_own_links(media_factory, page_count_sources):
    """A link to another host whose query names an id, such as a lookalike of Google, is not taken for a volume."""
    _openlibrary, googlebooks = page_count_sources
    media_factory(title="Lookalike", external_uri="https://notgoogle.com/books?id=vol1")

    call_command("fill_page_counts", stdout=StringIO())

    googlebooks.get_volume_details.assert_not_called()


def test_fill_page_counts_only_looks_for_the_missing_page_counts(media_factory, page_count_sources):
    """Media of other types, and books whose page count is known, are left as they are."""
    openlibrary, googlebooks = page_count_sources
    openlibrary.search_books.return_value = [_work("Anything", 999)]
    media_factory(title="Film", media_type="FILM")
    media_factory(title="Known", page_count=100)

    call_command("fill_page_counts", stdout=StringIO())

    assert dict(Media.objects.values_list("title", "page_count")) == {"Film": None, "Known": 100}
    openlibrary.search_books.assert_not_called()
    googlebooks.search_books.assert_not_called()


def test_fill_page_counts_goes_on_when_a_source_fails_or_is_not_configured(
    media_factory, page_count_sources, monkeypatch
):
    """A source that fails or Google Books without API key find nothing, and the other media are still looked for."""
    openlibrary, _googlebooks = page_count_sources
    openlibrary.search_books.side_effect = [APIError("down"), [_work("Dune", 412)]]
    monkeypatch.setattr(f"{FILL_PAGE_COUNTS}.get_googlebooks_client", lambda: None)
    media_factory(title="Anathem")
    media_factory(title="Dune")

    call_command("fill_page_counts", stdout=StringIO())

    assert dict(Media.objects.values_list("title", "page_count")) == {"Anathem": None, "Dune": 412}
