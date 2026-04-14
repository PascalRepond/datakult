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


def test_cover_url_builds_w500_url():
    """cover_url constructs the correct w500 image URL."""
    result = TMDBResult(
        tmdb_id=123,
        title="Test",
        original_title="Test",
        year=2024,
        overview="",
        cover_path="/abc123.jpg",
        media_type="movie",
    )

    assert result.cover_url == f"{TMDB_IMAGE_BASE_URL}w500/abc123.jpg"


def test_cover_url_returns_none_when_no_path():
    """cover_url returns None when cover_path is None."""
    result = TMDBResult(
        tmdb_id=123,
        title="Test",
        original_title="Test",
        year=2024,
        overview="",
        cover_path=None,
        media_type="movie",
    )

    assert result.cover_url is None


def test_cover_url_small_builds_w185_url():
    """cover_url_small constructs the correct w185 thumbnail URL."""
    result = TMDBResult(
        tmdb_id=123,
        title="Test",
        original_title="Test",
        year=2024,
        overview="",
        cover_path="/abc123.jpg",
        media_type="movie",
    )

    assert result.cover_url_small == f"{TMDB_IMAGE_BASE_URL}w185/abc123.jpg"


def test_raises_error_without_api_key(settings):
    """TMDBClient raises TMDBError when no API key is provided."""
    settings.TMDB_API_KEY = ""

    with pytest.raises(TMDBError) as exc_info:
        TMDBClient()

    assert "TMDB API key is required" in str(exc_info.value)


def test_search_returns_empty_for_short_query():
    """search_multi returns empty list for queries shorter than MIN_QUERY_LENGTH."""
    client = TMDBClient(api_key="test-key")

    # Query too short - no API call should be made
    result = client.search_multi("a")

    assert result == []
    assert len("a") < MIN_QUERY_LENGTH


def test_search_returns_empty_for_empty_query():
    """search_multi returns empty list for empty query."""
    client = TMDBClient(api_key="test-key")

    result = client.search_multi("")

    assert result == []
