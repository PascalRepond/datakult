"""
Tests for MusicBrainz integration in views.

These tests verify the application behavior, not the external API.
"""

from unittest.mock import MagicMock, patch

import requests
from django.urls import reverse

from core.services.musicbrainz import MusicBrainzResult


class TestMusicBrainzSearchView:
    """Tests for the musicbrainz_search_htmx view."""

    def test_returns_empty_for_short_query(self, logged_in_client):
        """Returns empty results for queries shorter than minimum length."""
        response = logged_in_client.get(reverse("musicbrainz_search_htmx"), {"q": "a"})

        assert response.status_code == 200
        assert "partials/musicbrainz/musicbrainz_suggestions.html" in [t.name for t in response.templates]
        assert response.context["results"] == []

    def test_returns_empty_for_empty_query(self, logged_in_client):
        """Returns empty results for empty query."""
        response = logged_in_client.get(reverse("musicbrainz_search_htmx"), {"q": ""})

        assert response.status_code == 200
        assert response.context["results"] == []

    @patch("core.views.get_musicbrainz_client")
    def test_returns_search_results(self, mock_get_client, logged_in_client):
        """Returns search results from MusicBrainz client."""
        mock_client = MagicMock()
        mock_client.search_releases.return_value = [
            MusicBrainzResult(
                mbid="test-mbid-123",
                title="Abbey Road",
                artists=["The Beatles"],
                year=1969,
                country="GB",
                label="Apple Records",
            )
        ]
        mock_get_client.return_value = mock_client

        response = logged_in_client.get(reverse("musicbrainz_search_htmx"), {"q": "abbey road"})

        assert response.status_code == 200
        assert len(response.context["results"]) == 1
        assert response.context["results"][0].title == "Abbey Road"
        mock_client.search_releases.assert_called_once()

    @patch("core.views.get_musicbrainz_client")
    def test_handles_api_error_gracefully(self, mock_get_client, logged_in_client):
        """Handles API errors gracefully and shows error message."""
        mock_client = MagicMock()
        mock_client.search_releases.side_effect = requests.RequestException("API Error")
        mock_get_client.return_value = mock_client

        response = logged_in_client.get(reverse("musicbrainz_search_htmx"), {"q": "test query"})

        assert response.status_code == 200
        assert "error" in response.context
        assert response.context["error"] == "Search failed"

    def test_preserves_media_id_in_context(self, logged_in_client):
        """Preserves media_id in context for editing existing media."""
        response = logged_in_client.get(reverse("musicbrainz_search_htmx"), {"q": "", "media_id": "42"})

        assert response.status_code == 200
        assert response.context["media_id"] == "42"

    @patch("core.views.get_musicbrainz_client")
    def test_preserves_query_in_context(self, mock_get_client, logged_in_client):
        """Preserves search query in context."""
        mock_client = MagicMock()
        mock_client.search_releases.return_value = []
        mock_get_client.return_value = mock_client

        response = logged_in_client.get(reverse("musicbrainz_search_htmx"), {"q": "test"})

        assert response.status_code == 200
        assert response.context["query"] == "test"
