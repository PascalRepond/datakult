"""
Tests for core.services.tmdb module.

These tests verify pure business logic without mocking API calls.
"""

import pytest

from core.services.tmdb import TMDB_IMAGE_BASE_URL, TMDBClient, TMDBError, TMDBResult


def _result(cover_path):
    return TMDBResult(
        tmdb_id=123,
        title="Test",
        original_title="Test",
        year=2024,
        overview="",
        cover_path=cover_path,
        media_type="movie",
    )


@pytest.mark.parametrize(
    ("cover_path", "cover_url", "cover_url_small"),
    [
        ("/abc123.jpg", f"{TMDB_IMAGE_BASE_URL}w500/abc123.jpg", f"{TMDB_IMAGE_BASE_URL}w185/abc123.jpg"),
        (None, None, None),
    ],
)
def test_cover_urls_are_built_from_the_cover_path(cover_path, cover_url, cover_url_small):
    """A result has a large and a small cover URL when TMDB gives it a cover path, and none otherwise."""
    result = _result(cover_path)

    assert (result.cover_url, result.cover_url_small) == (cover_url, cover_url_small)


def test_raises_error_without_api_key(settings):
    """TMDBClient raises TMDBError when no API key is provided."""
    settings.TMDB_API_KEY = ""

    with pytest.raises(TMDBError, match="TMDB API key is required"):
        TMDBClient()


@pytest.mark.parametrize("query", ["", "a"])
def test_search_returns_empty_for_short_query(query):
    """A query shorter than two characters searches nothing."""
    assert TMDBClient(api_key="test-key").search_multi(query, language="en-US") == []
