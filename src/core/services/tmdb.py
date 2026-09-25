"""
TMDB API client for fetching movie and TV show metadata.

API Documentation: https://developer.themoviedb.org/docs
"""

import logging
import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urljoin

from django.conf import settings

from .base import MIN_QUERY_LENGTH, APIClient, APIError, extract_year

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3/"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/"

# Fields of the title, the original title and the date, which differ between movies and TV shows
TITLE_FIELDS = {
    "movie": ("title", "original_title", "release_date"),
    "tv": ("name", "original_name", "first_air_date"),
}


class TMDBError(APIError):
    """Exception raised when the TMDB API key is missing."""

    def __init__(self) -> None:
        super().__init__("TMDB API key is required. Set TMDB_API_KEY in your environment.")


def _image_url(cover_path: str | None, size: str) -> str | None:
    """Return the URL of a TMDB image at one of its sizes, such as w500."""
    return f"{TMDB_IMAGE_BASE_URL}{size}{cover_path}" if cover_path else None


@dataclass
class TMDBResult:
    """Represents a search result from TMDB."""

    tmdb_id: int
    title: str
    original_title: str
    year: int | None
    overview: str
    cover_path: str | None
    media_type: Literal["movie", "tv"]

    @property
    def cover_url(self) -> str | None:
        """Returns the full URL for the cover image (w500 size)."""
        return _image_url(self.cover_path, "w500")

    @property
    def cover_url_small(self) -> str | None:
        """Returns a smaller cover URL for thumbnails (w185 size)."""
        return _image_url(self.cover_path, "w185")


class TMDBClient(APIClient):
    """Client for interacting with The Movie Database (TMDB) API."""

    source_name = "TMDB"
    cover_url_pattern = re.compile(re.escape(TMDB_IMAGE_BASE_URL))

    def __init__(self, api_key: str | None = None):
        super().__init__()
        self.api_key = api_key or settings.TMDB_API_KEY
        if not self.api_key:
            raise TMDBError

    def _get(self, endpoint: str, params: dict) -> dict:
        """Make a request to the TMDB API."""
        return self._request(urljoin(TMDB_BASE_URL, endpoint), params={**params, "api_key": self.api_key})

    def search_multi(self, query: str, language: str, page: int = 1) -> list[TMDBResult]:
        """
        Search for movies and TV shows.

        Args:
            query: The search query
            language: Language for results
            page: Page number for pagination

        Returns:
            List of TMDBResult objects
        """
        if not query or len(query) < MIN_QUERY_LENGTH:
            return []

        data = self._get(
            "search/multi",
            {"query": query, "language": language, "page": page, "include_adult": False},
        )

        results = []
        for item in data.get("results", []):
            media_type = item.get("media_type")
            if media_type not in TITLE_FIELDS:
                continue
            title_field, original_title_field, date_field = TITLE_FIELDS[media_type]
            results.append(
                TMDBResult(
                    tmdb_id=item.get("id"),
                    title=item.get(title_field, ""),
                    original_title=item.get(original_title_field, ""),
                    year=extract_year(item.get(date_field)),
                    overview=item.get("overview", ""),
                    cover_path=item.get("poster_path"),
                    media_type=media_type,
                )
            )

        return results

    def get_full_details(self, tmdb_id: int, media_type: Literal["movie", "tv"], language: str) -> dict:
        """
        Get full details for a movie or TV show including contributors.

        Returns a dict with:
            - title, year
            - contributors: directors, or creators of a TV show, then the main production companies
            - genres: list of genre names
            - cover_url: full URL for cover image
            - source_url: URL to TMDB page
            - media_type: "movie" or "tv"
        """
        data = self._get(f"{media_type}/{tmdb_id}", {"language": language, "append_to_response": "credits"})
        title_field, _original_title_field, date_field = TITLE_FIELDS[media_type]
        if media_type == "movie":
            directors = [p["name"] for p in data.get("credits", {}).get("crew", []) if p.get("job") == "Director"]
        else:
            directors = [p["name"] for p in data.get("created_by", [])]
        production_companies = [c["name"] for c in data.get("production_companies", [])[:2]]

        return {
            "title": data.get(title_field, ""),
            "year": extract_year(data.get(date_field)),
            "contributors": directors + production_companies,
            "genres": [g["name"] for g in data.get("genres", [])],
            "cover_url": _image_url(data.get("poster_path"), "w500"),
            "source_url": f"https://www.themoviedb.org/{media_type}/{tmdb_id}",
            "media_type": media_type,
        }


def get_tmdb_client() -> TMDBClient | None:
    """
    Factory function to get a TMDB client instance.

    Returns None if the API key is not configured.
    """
    if not settings.TMDB_API_KEY:
        logger.warning("TMDB API key not configured")
        return None
    return TMDBClient()
