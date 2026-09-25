"""
Tests for core.services.base module.

These tests verify the behaviour shared by the clients of every metadata source, through the OpenLibrary client.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests

from core.services.base import extract_year
from core.services.openlibrary import OpenLibraryClient

COVER_URL = "https://covers.openlibrary.org/b/id/42-L.jpg"
COVER = b"cover" * 1000


@pytest.mark.parametrize(
    ("date", "expected"),
    [
        ("2020", 2020),
        ("2020-05", 2020),
        ("2020-05-12", 2020),
        ("", None),
        (None, None),
        ("n/a", None),
        ("published in 1999", None),  # only leading YYYY is matched
    ],
)
def test_extract_year(date, expected):
    """The year of a date is its leading four digits."""
    assert extract_year(date) == expected


def _download(response):
    """Download the cover of COVER_URL, answered with the given response, and return it with the mocked GET."""
    client = OpenLibraryClient()
    with patch.object(client.session, "get", return_value=response) as get:
        return client.download_cover(COVER_URL), get


def test_download_cover_returns_the_cover_of_the_source():
    """A cover of the image server of the source is downloaded."""
    cover, _get = _download(MagicMock(status_code=200, content=COVER))

    assert cover == COVER


@pytest.mark.parametrize("url", ["", "https://example.com/covers/42-L.jpg"])
def test_download_cover_only_reaches_the_source(url):
    """No cover is downloaded without a URL, or from another server than the one of the source."""
    client = OpenLibraryClient()

    with patch.object(client.session, "get") as get:
        assert client.download_cover(url) is None
    get.assert_not_called()


@pytest.mark.parametrize(
    "response",
    [
        MagicMock(status_code=200, content=b"GIF89a"),
        MagicMock(status_code=404, content=b""),
        MagicMock(status_code=500, raise_for_status=MagicMock(side_effect=requests.HTTPError)),
    ],
    ids=["placeholder", "missing", "error"],
)
def test_download_cover_without_a_cover_returns_nothing(response):
    """A placeholder, a missing cover or a server error give no cover."""
    cover, _get = _download(response)

    assert cover is None
