"""
Tests for the Google Books service and the unified book search view.

These tests verify application behavior, not the external API.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests
from django.urls import reverse

from core.services.googlebooks import (
    GoogleBooksResult,
    _extract_year,
    _resize_cover_url,
    _strip_html,
)
from core.services.openlibrary import OpenLibraryResult

# ---------- Pure helpers ----------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2020", 2020),
        ("2020-05", 2020),
        ("2020-05-12", 2020),
        ("", None),
        ("n/a", None),
        ("published in 1999", None),  # only leading YYYY is matched
    ],
)
def test_extract_year(raw, expected):
    assert _extract_year(raw) == expected


def test_strip_html_removes_tags_and_decodes_entities():
    assert _strip_html("<p>Hello <b>world</b></p>") == "Hello world"
    assert _strip_html("Text &amp; entity") == "Text & entity"
    assert _strip_html("") == ""


def test_strip_html_turns_block_tags_into_newlines():
    result = _strip_html("Line1<br>Line2<p>Line3</p>")
    assert "Line1" in result
    assert "Line2" in result
    assert "Line3" in result


def test_resize_cover_url_replaces_zoom_with_fife():
    url = "http://books.google.com/books/content?id=ABC&zoom=1&edge=curl"
    upgraded = _resize_cover_url(url, "w800-h1200")
    assert upgraded.startswith("https://")
    assert "fife=w800-h1200" in upgraded
    assert "zoom=" not in upgraded
    assert "edge=curl" not in upgraded


def test_resize_cover_url_appends_fife_when_no_zoom():
    url = "https://books.google.com/books/content?id=ABC"
    upgraded = _resize_cover_url(url, "w128-h192")
    assert "fife=w128-h192" in upgraded


def test_resize_cover_url_handles_empty():
    assert _resize_cover_url("", "w800-h1200") == ""


# ---------- GoogleBooksResult properties ----------


def test_result_exposes_source_discriminator():
    r = GoogleBooksResult(volume_id="X", title="T", authors=[], year=None, thumbnail_url=None)
    assert r.source == "googlebooks"


def test_result_cover_urls_use_fife_sizing():
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
    r = GoogleBooksResult(volume_id="X", title="T", authors=[], year=None, thumbnail_url=None)
    assert r.cover_url is None
    assert r.cover_url_small is None
    assert r.cover_url_large is None


# ---------- book_search_htmx view ----------


def test_search_returns_empty_for_short_query(logged_in_client):
    response = logged_in_client.get(reverse("book_search_htmx"), {"q": "a"})

    assert response.status_code == 200
    assert "partials/book/book_suggestions.html" in [t.name for t in response.templates]
    assert response.context["results"] == []


def test_search_returns_empty_for_empty_query(logged_in_client):
    response = logged_in_client.get(reverse("book_search_htmx"), {"q": ""})

    assert response.status_code == 200
    assert response.context["results"] == []


def _make_ol(title, year=2020):
    return OpenLibraryResult(work_key=f"/works/OL{title}W", title=title, authors=["OL Author"], year=year, cover_id=1)


def _make_gb(title, year=2020):
    return GoogleBooksResult(
        volume_id=f"vol-{title}", title=title, authors=["GB Author"], year=year, thumbnail_url=None
    )


@patch("core.views.get_googlebooks_client")
@patch("core.views.get_openlibrary_client")
def test_search_interleaves_results_leading_with_googlebooks(mock_ol, mock_gb, logged_in_client):
    """Merged list alternates sources, Google Books first."""
    mock_ol.return_value.search_books.return_value = [_make_ol("OL1"), _make_ol("OL2")]
    mock_gb.return_value.search_books.return_value = [_make_gb("GB1"), _make_gb("GB2")]

    response = logged_in_client.get(reverse("book_search_htmx"), {"q": "test"})

    titles = [r.title for r in response.context["results"]]
    assert titles == ["GB1", "OL1", "GB2", "OL2"]


@patch("core.views.get_googlebooks_client")
@patch("core.views.get_openlibrary_client")
def test_search_falls_back_when_googlebooks_fails(mock_ol, mock_gb, logged_in_client):
    """OpenLibrary results still render when Google Books raises."""
    mock_ol.return_value.search_books.return_value = [_make_ol("OL1")]
    mock_gb.return_value.search_books.side_effect = requests.RequestException("boom")

    response = logged_in_client.get(reverse("book_search_htmx"), {"q": "test"})

    assert response.status_code == 200
    assert "error" not in response.context
    titles = [r.title for r in response.context["results"]]
    assert titles == ["OL1"]


@patch("core.views.get_googlebooks_client")
@patch("core.views.get_openlibrary_client")
def test_search_falls_back_when_openlibrary_fails(mock_ol, mock_gb, logged_in_client):
    """Google Books results still render when OpenLibrary raises."""
    mock_ol.return_value.search_books.side_effect = requests.RequestException("boom")
    mock_gb.return_value.search_books.return_value = [_make_gb("GB1")]

    response = logged_in_client.get(reverse("book_search_htmx"), {"q": "test"})

    assert response.status_code == 200
    assert "error" not in response.context
    titles = [r.title for r in response.context["results"]]
    assert titles == ["GB1"]


@patch("core.views.get_googlebooks_client")
@patch("core.views.get_openlibrary_client")
def test_search_surfaces_error_only_when_both_sources_fail(mock_ol, mock_gb, logged_in_client):
    mock_ol.return_value.search_books.side_effect = requests.RequestException("boom")
    mock_gb.return_value.search_books.side_effect = requests.RequestException("boom")

    response = logged_in_client.get(reverse("book_search_htmx"), {"q": "test"})

    assert response.status_code == 200
    assert response.context["error"] == "Search failed"
    assert response.context["results"] == []


@patch("core.views.get_googlebooks_client")
@patch("core.views.get_openlibrary_client")
def test_search_preserves_media_id_and_query_in_context(mock_ol, mock_gb, logged_in_client):
    mock_ol.return_value.search_books.return_value = []
    mock_gb.return_value.search_books.return_value = []

    response = logged_in_client.get(reverse("book_search_htmx"), {"q": "hello", "media_id": "42"})

    assert response.status_code == 200
    assert response.context["media_id"] == "42"
    assert response.context["query"] == "hello"


# ---------- get_volume_details: user-ID escaping (defense-in-depth) ----------


def test_get_volume_details_escapes_volume_id_in_path():
    """A malicious volume_id must be percent-encoded, not injected raw into the URL path."""
    from core.services.googlebooks import GoogleBooksClient

    client = GoogleBooksClient()

    response = MagicMock()
    response.json.return_value = {"volumeInfo": {}}
    response.raise_for_status.return_value = None

    with patch.object(client.session, "get", return_value=response) as mock_get:
        client.get_volume_details("../evil/path")

    called_url = mock_get.call_args[0][0]
    # Slashes in user input must not survive into the URL path
    assert "/volumes/../evil/path" not in called_url
    assert "%2F" in called_url or "%2f" in called_url
