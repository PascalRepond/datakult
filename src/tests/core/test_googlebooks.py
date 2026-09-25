"""
Tests for the Google Books service and the unified book search view.

These tests verify application behavior, not the external API.
"""

from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse

from core.services.base import APIError
from core.services.googlebooks import GoogleBooksClient, GoogleBooksResult, _resize_cover_url, get_googlebooks_client
from core.services.openlibrary import OpenLibraryResult

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


# ---------- book search view ----------


def _make_ol(title, year=2020):
    return OpenLibraryResult(work_key=f"/works/OL{title}W", title=title, authors=["OL Author"], year=year, cover_id=1)


def _make_gb(title, year=2020):
    return GoogleBooksResult(
        volume_id=f"vol-{title}", title=title, authors=["GB Author"], year=year, thumbnail_url=None
    )


@pytest.fixture
def book_clients(monkeypatch):
    """Replace the OpenLibrary and Google Books clients of the book search by mocks, returned in that order."""
    openlibrary, googlebooks = MagicMock(), MagicMock()
    monkeypatch.setattr("core.views.get_openlibrary_client", lambda: openlibrary)
    monkeypatch.setattr("core.views.get_googlebooks_client", lambda: googlebooks)
    return openlibrary, googlebooks


def _search_books(client, **params):
    return client.get(reverse("import_search_htmx"), {"source": "books", "q": "test", **params})


def test_search_interleaves_results_leading_with_googlebooks(logged_in_client, book_clients):
    """Merged list alternates sources, Google Books first."""
    openlibrary, googlebooks = book_clients
    openlibrary.search_books.return_value = [_make_ol("OL1"), _make_ol("OL2")]
    googlebooks.search_books.return_value = [_make_gb("GB1"), _make_gb("GB2")]

    response = _search_books(logged_in_client)

    assert [r.title for r in response.context["results"]] == ["GB1", "OL1", "GB2", "OL2"]


def test_search_falls_back_when_googlebooks_fails(logged_in_client, book_clients):
    """OpenLibrary results still render when Google Books raises."""
    openlibrary, googlebooks = book_clients
    openlibrary.search_books.return_value = [_make_ol("OL1")]
    googlebooks.search_books.side_effect = APIError("boom")

    response = _search_books(logged_in_client)

    assert "error" not in response.context
    assert [r.title for r in response.context["results"]] == ["OL1"]
    assert "Google Books" in response.context["notice"]


def test_search_falls_back_when_openlibrary_fails(logged_in_client, book_clients):
    """Google Books results still render when OpenLibrary raises."""
    openlibrary, googlebooks = book_clients
    openlibrary.search_books.side_effect = APIError("boom")
    googlebooks.search_books.return_value = [_make_gb("GB1")]

    response = _search_books(logged_in_client)

    assert "error" not in response.context
    assert [r.title for r in response.context["results"]] == ["GB1"]
    assert "OpenLibrary" in response.context["notice"]


def test_search_surfaces_error_only_when_both_sources_fail(logged_in_client, book_clients):
    """The search fails only when neither source could be searched."""
    for book_client in book_clients:
        book_client.search_books.side_effect = APIError("boom")

    response = _search_books(logged_in_client)

    assert response.context["error"] == "Search failed"
    assert response.context["results"] == []


def test_search_preserves_media_id_and_query_in_context(logged_in_client, book_clients):
    """The results keep the media being edited and the query, for their import links."""
    for book_client in book_clients:
        book_client.search_books.return_value = []

    response = _search_books(logged_in_client, q="hello", media_id="42")

    assert response.context["media_id"] == "42"
    assert response.context["query"] == "hello"


def test_search_without_googlebooks_says_it_is_not_configured(logged_in_client, book_clients, monkeypatch):
    """Without Google Books, the book search shows the results of OpenLibrary, and says how to add Google Books."""
    openlibrary, _googlebooks = book_clients
    openlibrary.search_books.return_value = [_make_ol("OL1")]
    monkeypatch.setattr("core.views.get_googlebooks_client", lambda: None)

    response = _search_books(logged_in_client)

    assert [r.title for r in response.context["results"]] == ["OL1"]
    assert "GOOGLE_BOOKS_API_KEY" in response.context["notice"]
    assert response.context["notice"] in response.content.decode()


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
