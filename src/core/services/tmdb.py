"""
TMDB API client for fetching movie and TV show metadata.

API Documentation: https://developer.themoviedb.org/docs
"""

import logging
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlencode, urljoin

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3/"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/"

# Minimum query length for search
MIN_QUERY_LENGTH = 2
# Minimum date string length for year extraction (YYYY)
MIN_DATE_LENGTH = 4


class TMDBError(Exception):
    """Exception raised when TMDB API key is missing or invalid."""

    def __init__(self) -> None:
        super().__init__("TMDB API key is required. Set TMDB_API_KEY in your environment.")


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
        if self.cover_path:
            return f"{TMDB_IMAGE_BASE_URL}w500{self.cover_path}"
        return None

    @property
    def cover_url_small(self) -> str | None:
        """Returns a smaller cover URL for thumbnails (w185 size)."""
        if self.cover_path:
            return f"{TMDB_IMAGE_BASE_URL}w185{self.cover_path}"
        return None


class TMDBClient:
    """Client for interacting with The Movie Database (TMDB) API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.TMDB_API_KEY
        if not self.api_key:
            raise TMDBError

    def _request(self, endpoint: str, params: dict | None = None) -> dict:
        """Make a request to the TMDB API."""
        params = params or {}
        params["api_key"] = self.api_key

        url = urljoin(TMDB_BASE_URL, endpoint)
        full_url = f"{url}?{urlencode(params)}"

        try:
            response = requests.get(full_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            logger.exception("TMDB API request failed")
            raise

    def search_multi(self, query: str, language: str = "fr-FR", page: int = 1) -> list[TMDBResult]:
        """
        Search for movies and TV shows.

        Args:
            query: The search query
            language: Language for results (default: French)
            page: Page number for pagination

        Returns:
            List of TMDBResult objects
        """
        if not query or len(query) < MIN_QUERY_LENGTH:
            return []

        data = self._request(
            "search/multi",
            {"query": query, "language": language, "page": page, "include_adult": False},
        )

        results = []
        for item in data.get("results", []):
            media_type = item.get("media_type")
            if media_type not in ("movie", "tv"):
                continue

            if media_type == "movie":
                title = item.get("title", "")
                original_title = item.get("original_title", "")
                date_field = item.get("release_date", "")
            else:
                title = item.get("name", "")
                original_title = item.get("original_name", "")
                date_field = item.get("first_air_date", "")

            year = int(date_field[:4]) if date_field and len(date_field) >= MIN_DATE_LENGTH else None

            results.append(
                TMDBResult(
                    tmdb_id=item.get("id"),
                    title=title,
                    original_title=original_title,
                    year=year,
                    overview=item.get("overview", ""),
                    cover_path=item.get("poster_path"),
                    media_type=media_type,
                )
            )

        return results

    def get_movie_details(self, movie_id: int, language: str = "fr-FR") -> dict:
        """Get detailed information about a movie, including credits and production companies."""
        return self._request(f"movie/{movie_id}", {"language": language, "append_to_response": "credits"})

    def get_tv_details(self, tv_id: int, language: str = "fr-FR") -> dict:
        """Get detailed information about a TV show, including credits and production companies."""
        return self._request(f"tv/{tv_id}", {"language": language, "append_to_response": "credits"})

    def get_full_details(self, tmdb_id: int, media_type: Literal["movie", "tv"], language: str = "fr-FR") -> dict:
        """
        Get full details for a movie or TV show including contributors.

        Returns a dict with:
            - title, original_title, year, overview
            - directors: list of director names
            - production_companies: list of company names
            - cover_url: full URL for cover image
            - tmdb_url: URL to TMDB page
        """
        if media_type == "movie":
            data = self.get_movie_details(tmdb_id, language)
            title = data.get("title", "")
            original_title = data.get("original_title", "")
            date_field = data.get("release_date", "")
            # Get directors from crew
            crew = data.get("credits", {}).get("crew", [])
            directors = [p["name"] for p in crew if p.get("job") == "Director"]
        else:
            data = self.get_tv_details(tmdb_id, language)
            title = data.get("name", "")
            original_title = data.get("original_name", "")
            date_field = data.get("first_air_date", "")
            # For TV shows, get creators instead of directors
            directors = [p["name"] for p in data.get("created_by", [])]

        year = int(date_field[:4]) if date_field and len(date_field) >= MIN_DATE_LENGTH else None

        # Get production companies
        production_companies = [c["name"] for c in data.get("production_companies", [])[:2]]

        # Get genres
        genres = [g["name"] for g in data.get("genres", [])]

        # Build cover URL
        cover_path = data.get("poster_path")
        cover_url = f"{TMDB_IMAGE_BASE_URL}w500{cover_path}" if cover_path else None

        # Build TMDB URL
        tmdb_url = f"https://www.themoviedb.org/{media_type}/{tmdb_id}"

        return {
            "title": title,
            "original_title": original_title,
            "year": year,
            "overview": data.get("overview", ""),
            "directors": directors,
            "production_companies": production_companies,
            "genres": genres,
            "cover_url": cover_url,
            "tmdb_url": tmdb_url,
            "media_type": media_type,
        }

    def download_cover(self, cover_url: str) -> bytes | None:
        """Download cover image and return bytes."""
        if not cover_url:
            return None

        # Validate URL is from TMDB image CDN
        if not cover_url.startswith(TMDB_IMAGE_BASE_URL):
            logger.warning("Invalid TMDB cover URL: %s", cover_url)
            return None

        try:
            response = requests.get(cover_url, timeout=15)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Failed to download cover from %s", cover_url)
            return None

        return response.content


def get_tmdb_client() -> TMDBClient | None:
    """
    Factory function to get a TMDB client instance.

    Returns None if the API key is not configured.
    """
    if not settings.TMDB_API_KEY:
        logger.warning("TMDB API key not configured")
        return None
    return TMDBClient()
