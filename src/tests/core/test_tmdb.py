"""
Tests for core.services.tmdb module.

These tests verify pure business logic without mocking API calls.
"""

import pytest

from core.services.tmdb import (
    MIN_QUERY_LENGTH,
    TMDB_IMAGE_BASE_URL,
    TMDBClient,
    TMDBError,
    TMDBResult,
)


class TestTMDBResult:
    """Tests for the TMDBResult dataclass poster URL generation."""

    def test_poster_url_builds_w500_url(self):
        """poster_url constructs the correct w500 image URL."""
        result = TMDBResult(
            tmdb_id=123,
            title="Test",
            original_title="Test",
            year=2024,
            overview="",
            poster_path="/abc123.jpg",
            media_type="movie",
        )

        assert result.poster_url == f"{TMDB_IMAGE_BASE_URL}w500/abc123.jpg"

    def test_poster_url_returns_none_when_no_path(self):
        """poster_url returns None when poster_path is None."""
        result = TMDBResult(
            tmdb_id=123,
            title="Test",
            original_title="Test",
            year=2024,
            overview="",
            poster_path=None,
            media_type="movie",
        )

        assert result.poster_url is None

    def test_poster_url_small_builds_w185_url(self):
        """poster_url_small constructs the correct w185 thumbnail URL."""
        result = TMDBResult(
            tmdb_id=123,
            title="Test",
            original_title="Test",
            year=2024,
            overview="",
            poster_path="/abc123.jpg",
            media_type="movie",
        )

        assert result.poster_url_small == f"{TMDB_IMAGE_BASE_URL}w185/abc123.jpg"


class TestTMDBClientValidation:
    """Tests for TMDBClient input validation."""

    def test_raises_error_without_api_key(self, settings):
        """TMDBClient raises TMDBError when no API key is provided."""
        settings.TMDB_API_KEY = ""

        with pytest.raises(TMDBError) as exc_info:
            TMDBClient()

        assert "TMDB API key is required" in str(exc_info.value)

    def test_search_returns_empty_for_short_query(self):
        """search_multi returns empty list for queries shorter than MIN_QUERY_LENGTH."""
        client = TMDBClient(api_key="test-key")

        # Query too short - no API call should be made
        result = client.search_multi("a")

        assert result == []
        assert len("a") < MIN_QUERY_LENGTH

    def test_search_returns_empty_for_empty_query(self):
        """search_multi returns empty list for empty query."""
        client = TMDBClient(api_key="test-key")

        result = client.search_multi("")

        assert result == []
