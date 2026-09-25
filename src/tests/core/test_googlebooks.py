"""
Tests for core.services.googlebooks module.

These tests verify application behavior, not the external API.
"""

from unittest.mock import MagicMock, patch

import pytest

from core.services.googlebooks import GoogleBooksClient, GoogleBooksResult, _resize_cover_url, get_googlebooks_client

# ---------- Pure helpers ----------


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "http://books.google.com/books/content?id=ABC&zoom=1&edge=curl",
            "https://books.google.com/books/content?id=ABC&fife=w800-h1200",
        ),
        (
            "https://books.google.com/books/content?id=ABC",
            "https://books.google.com/books/content?id=ABC&fife=w800-h1200",
        ),
        ("", ""),
    ],
    ids=["zoom", "no zoom", "empty"],
)
def test_resize_cover_url_asks_for_the_given_size(url, expected):
    """Cover URLs are served over HTTPS at the given size, instead of their zoom level and curled edge."""
    assert _resize_cover_url(url, "w800-h1200") == expected


# ---------- GoogleBooksResult properties ----------


def test_result_cover_urls_use_fife_sizing():
    """The covers of a result are served over HTTPS at a large and a small size."""
    r = GoogleBooksResult(
        volume_id="X",
        title="T",
        authors=[],
        year=None,
        thumbnail_url="http://books.google.com/books/content?id=X&zoom=1",
    )
    assert r.cover_url is not None
    assert "fife=w800-h1200" in r.cover_url
    assert r.cover_url.startswith("https://")
    assert r.cover_url_small is not None
    assert "fife=w128-h192" in r.cover_url_small


def test_result_cover_urls_none_without_thumbnail():
    """A result without thumbnail has no cover."""
    r = GoogleBooksResult(volume_id="X", title="T", authors=[], year=None, thumbnail_url=None)
    assert r.cover_url is None
    assert r.cover_url_small is None


# ---------- Google Books client ----------


def test_get_volume_details_escapes_volume_id_in_path():
    """A malicious volume_id must be percent-encoded, not injected raw into the URL path."""
    client = GoogleBooksClient(api_key="")
    response = MagicMock()
    response.json.return_value = {"volumeInfo": {}}

    with patch.object(client.session, "request", return_value=response) as mock_request:
        client.get_volume_details("../evil/path")

    called_url = mock_request.call_args.args[1]
    assert "/volumes/../evil/path" not in called_url
    assert "%2F" in called_url


@pytest.mark.parametrize(("api_key", "sent"), [("secret", True), ("", False)])
def test_requests_carry_the_api_key(api_key, sent):
    """The API key, when there is one, goes with every request, as Google Books refuses anonymous ones."""
    client = GoogleBooksClient(api_key=api_key)
    response = MagicMock()
    response.json.return_value = {"items": []}

    with patch.object(client.session, "request", return_value=response) as mock_request:
        client.search_books("dune")

    assert (mock_request.call_args.kwargs["params"].get("key") == "secret") is sent


def test_client_needs_an_api_key(settings):
    """Without an API key, there is no Google Books client, as its requests would all be refused."""
    settings.GOOGLE_BOOKS_API_KEY = ""
    assert get_googlebooks_client() is None

    settings.GOOGLE_BOOKS_API_KEY = "secret"
    assert get_googlebooks_client().api_key == "secret"
