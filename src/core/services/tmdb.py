"""
TMDB API client for fetching movie and TV show metadata.

API Documentation: https://developer.themoviedb.org/docs
"""

import ipaddress
import logging
import re
import socket
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlencode, urljoin, urlparse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3/"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/"

# Allowed hosts for TMDB image downloads (SSRF protection)
TMDB_ALLOWED_IMAGE_HOSTS = frozenset({"image.tmdb.org"})
# Pattern for valid TMDB poster paths (e.g., /t/p/w500/abc123.jpg)
TMDB_POSTER_PATH_PATTERN = re.compile(r"^/t/p/w\d+/[a-zA-Z0-9]+\.[a-z]{3,4}$")

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
    poster_path: str | None
    media_type: Literal["movie", "tv"]

    @property
    def poster_url(self) -> str | None:
        """Returns the full URL for the poster image (w500 size)."""
        if self.poster_path:
            return f"{TMDB_IMAGE_BASE_URL}w500{self.poster_path}"
        return None

    @property
    def poster_url_small(self) -> str | None:
        """Returns a smaller poster URL for thumbnails (w185 size)."""
        if self.poster_path:
            return f"{TMDB_IMAGE_BASE_URL}w185{self.poster_path}"
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
                    poster_path=item.get("poster_path"),
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
            - poster_url: full URL for poster image
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

        # Build poster URL
        poster_path = data.get("poster_path")
        poster_url = f"{TMDB_IMAGE_BASE_URL}w500{poster_path}" if poster_path else None

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
            "poster_url": poster_url,
            "tmdb_url": tmdb_url,
            "media_type": media_type,
        }

    def _validate_poster_url(self, poster_url: str) -> bool:
        """
        Validate that the poster URL is a legitimate TMDB image URL.

        Returns True if the URL is valid and safe to fetch, False otherwise.
        """
        try:
            parsed = urlparse(poster_url)
        except ValueError:
            logger.warning("Invalid URL format rejected: %s", poster_url)
            return False

        # Validate scheme, host, and path pattern
        if parsed.scheme != "https":
            logger.warning("Non-HTTPS URL rejected: %s", poster_url)
            return False
        if parsed.hostname not in TMDB_ALLOWED_IMAGE_HOSTS:
            logger.warning("URL with disallowed host rejected: %s", poster_url)
            return False
        if not TMDB_POSTER_PATH_PATTERN.match(parsed.path):
            logger.warning("URL with invalid path pattern rejected: %s", poster_url)
            return False

        # DNS resolution check: reject private/reserved IP ranges
        return self._validate_resolved_ip(poster_url, parsed.hostname)

    def _validate_resolved_ip(self, poster_url: str, hostname: str) -> bool:
        """Check that hostname does not resolve to private/reserved IP ranges."""
        try:
            resolved_ips = socket.getaddrinfo(hostname, 443, proto=socket.IPPROTO_TCP)
            for _, _, _, _, sockaddr in resolved_ips:
                ip_str = sockaddr[0]
                ip = ipaddress.ip_address(ip_str)
                if ip.is_private or ip.is_reserved or ip.is_loopback or ip.is_link_local:
                    logger.warning("URL resolving to private/reserved IP rejected: %s -> %s", poster_url, ip_str)
                    return False
        except (socket.gaierror, ValueError) as e:
            logger.warning("DNS resolution failed for URL %s: %s", poster_url, e)
            return False
        return True

    def download_poster(self, poster_url: str) -> bytes | None:
        """
        Download poster image and return bytes.

        Validates the URL against TMDB allowlist and performs security checks
        to prevent SSRF attacks before downloading.
        """
        if not poster_url:
            return None

        if not self._validate_poster_url(poster_url):
            return None

        try:
            response = requests.get(poster_url, timeout=15, allow_redirects=False)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Failed to download poster from %s", poster_url)
            return None

        # Check for redirect responses (3xx status codes)
        if response.is_redirect or response.is_permanent_redirect:
            logger.warning("Redirect response rejected for URL: %s", poster_url)
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
