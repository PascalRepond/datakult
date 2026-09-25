"""
Tests for core.views.backup: the export and import of backups.
"""

import json
import re
import tarfile
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import CommandError
from django.urls import reverse

from core.models import Media
from core.utils import create_backup
from tests.helpers import messages_of


def test_backup_export_downloads_a_backup_left_nowhere_on_the_server(logged_in_client, media, settings, tmp_path):
    """The exported backup holds the data, and is sent without leaving a copy among the backups of the server."""
    settings.BASE_DIR = tmp_path / "app"

    response = logged_in_client.get(reverse("backup_export"))

    with tarfile.open(fileobj=BytesIO(b"".join(response.streaming_content))) as tar:
        database = json.loads(tar.extractfile("database.json").read())
    assert [entry["fields"]["title"] for entry in database if entry["model"] == "core.media"] == ["Test Media"]
    # Django's FileResponse detects .tar.gz as gzip
    assert response["Content-Type"] == "application/gzip"
    assert re.fullmatch(r'attachment; filename="datakult_backup_[\d_]+\.tar\.gz"', response["Content-Disposition"])
    assert not list(tmp_path.rglob("*.tar.gz"))


@pytest.mark.parametrize("error", [OSError, CommandError])
def test_backup_export_failure_is_reported_once(logged_in_client, monkeypatch, error):
    """A failed export goes back to the backup page, where its error is shown only once, as a toast."""

    def failing_backup(fileobj):
        msg = "Disk full"
        raise error(msg)

    monkeypatch.setattr("core.views.backup.write_backup", failing_backup)

    response = logged_in_client.get(reverse("backup_export"), follow=True)

    assert response.redirect_chain == [(reverse("backup_manage"), 302)]
    assert response.content.decode().count("Disk full") == 1


def test_backup_import_get_redirects(logged_in_client):
    """GET requests to backup import redirect to backup manage."""
    response = logged_in_client.get(reverse("backup_import"))

    assert response.url == reverse("backup_manage")


@pytest.mark.parametrize(
    "upload",
    [None, ("backup.txt", b"not a backup"), ("backup.tar.gz", b"invalid content")],
    ids=["no file", "not an archive", "invalid archive"],
)
def test_backup_import_rejects_what_is_not_a_backup(logged_in_client, upload):
    """Importing no file, or a file that is not a valid backup, goes back to the backup page with an error."""
    data = {"backup_file": SimpleUploadedFile(*upload)} if upload else {}

    response = logged_in_client.post(reverse("backup_import"), data)

    assert response.url == reverse("backup_manage")
    assert messages_of(response)


def test_backup_import_restores_data(logged_in_client, media_factory, tmp_path):
    """The backup import view successfully restores data from a backup."""
    media_factory(title="Original Media", status="COMPLETED")
    backup_path = create_backup(output_dir=tmp_path)
    Media.objects.all().delete()

    uploaded_file = SimpleUploadedFile(backup_path.name, backup_path.read_bytes(), content_type="application/x-tar")
    response = logged_in_client.post(reverse("backup_import"), {"backup_file": uploaded_file})

    assert response.url == reverse("home")
    assert list(Media.objects.values_list("title", "status")) == [("Original Media", "COMPLETED")]


def test_backup_page_has_no_inline_script(logged_in_client):
    """The backup page exports through a plain link, and leaves the import check to a static script."""
    content = logged_in_client.get(reverse("backup_manage")).content.decode()
    body = content.split("</head>")[1]

    assert re.search(rf'<a href="{reverse("backup_export")}"', body)
    assert "js/backup_manage.js" in body
    assert "<script>" not in body
    assert not re.search(r"\sonclick=", body)
