"""
Tests for MusicBrainz integration in views.

These tests verify the application behavior, not the external API.
"""

from unittest.mock import MagicMock

import pytest
import requests
from django.urls import reverse

from core.services.musicbrainz import MusicBrainzResult


@pytest.fixture
def musicbrainz_client(monkeypatch):
    """Replace the MusicBrainz client of the music search by a mock."""
    client = MagicMock()
    monkeypatch.setattr("core.views.get_musicbrainz_client", lambda: client)
    return client


def _search_music(client, **params):
    return client.get(reverse("import_search_htmx"), {"source": "musicbrainz", **params})


def test_returns_search_results(logged_in_client, musicbrainz_client):
    """The music search shows the releases found by MusicBrainz."""
    musicbrainz_client.search_releases.return_value = [
        MusicBrainzResult(
            mbid="test-mbid-123",
            title="Abbey Road",
            artists=["The Beatles"],
            year=1969,
            country="GB",
            label="Apple Records",
        )
    ]

    response = _search_music(logged_in_client, q="abbey road")

    assert [result.title for result in response.context["results"]] == ["Abbey Road"]


def test_handles_api_error_gracefully(logged_in_client, musicbrainz_client):
    """Handles API errors gracefully and shows error message."""
    musicbrainz_client.search_releases.side_effect = requests.RequestException("API Error")

    response = _search_music(logged_in_client, q="test query")

    assert response.context["error"] == "Search failed"


def test_preserves_media_id_and_query_in_context(logged_in_client, musicbrainz_client):
    """The results keep the media being edited and the query, for their import links."""
    musicbrainz_client.search_releases.return_value = []

    response = _search_music(logged_in_client, q="test", media_id="42")

    assert response.context["media_id"] == "42"
    assert response.context["query"] == "test"
