"""
MusicBrainz API client for fetching music album metadata.

API Documentation: https://musicbrainz.org/doc/MusicBrainz_API
Cover Art Archive: https://coverartarchive.org/

This API is free and does not require authentication.
Rate limiting: 1 request per second with a proper User-Agent header.
"""

import logging
import re
from dataclasses import dataclass
from http import HTTPStatus

import requests

logger = logging.getLogger(__name__)

MUSICBRAINZ_BASE_URL = "https://musicbrainz.org/ws/2/"
COVERART_BASE_URL = "https://coverartarchive.org/"

# User-Agent is required by MusicBrainz API
USER_AGENT = "Datakult/1.0 (personal media tracker)"

# Minimum query length for search
MIN_QUERY_LENGTH = 2

# Pattern for valid Cover Art Archive URLs
COVERART_PATTERN = re.compile(r"^https://coverartarchive\.org/release/[a-f0-9-]+/")

# Minimum size in bytes to consider a cover valid
MIN_COVER_SIZE_BYTES = 1000


class MusicBrainzError(Exception):
    """Exception raised when MusicBrainz API request fails."""


def _extract_artists(data: dict) -> list[str]:
    """Extract artist names from artist-credit data."""
    return [ac["name"] for ac in data.get("artist-credit", []) if isinstance(ac, dict) and "name" in ac]


def _extract_year(date_str: str) -> int | None:
    """Extract year from a date string."""
    if not date_str:
        return None
    year_match = re.match(r"(\d{4})", date_str)
    return int(year_match.group(1)) if year_match else None


def _extract_label(label_info: list) -> str | None:
    """Extract label name from label-info data."""
    if not label_info or not isinstance(label_info[0], dict):
        return None
    label_data = label_info[0].get("label", {})
    return label_data.get("name") if label_data else None


def _extract_genres_and_tags(data: dict) -> list[str]:
    """Extract unique genre and tag names."""
    genres = [g["name"] for g in data.get("genres", []) if isinstance(g, dict) and "name" in g]
    for tag in data.get("tags", []):
        if isinstance(tag, dict) and "name" in tag and tag["name"] not in genres:
            genres.append(tag["name"])
    return genres


@dataclass
class MusicBrainzResult:
    """Represents a search result from MusicBrainz."""

    mbid: str  # MusicBrainz ID (UUID)
    title: str
    artists: list[str]
    year: int | None
    country: str | None
    label: str | None

    @property
    def cover_url(self) -> str | None:
        """Returns the URL for the cover image (front, 500px)."""
        if self.mbid:
            return f"{COVERART_BASE_URL}release/{self.mbid}/front-500"
        return None

    @property
    def cover_url_small(self) -> str | None:
        """Returns a smaller cover URL for thumbnails (250px)."""
        if self.mbid:
            return f"{COVERART_BASE_URL}release/{self.mbid}/front-250"
        return None

    @property
    def cover_url_large(self) -> str | None:
        """Returns the full-size cover URL."""
        if self.mbid:
            return f"{COVERART_BASE_URL}release/{self.mbid}/front"
        return None


class MusicBrainzClient:
    """Client for interacting with the MusicBrainz API."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            }
        )

    def _request(self, endpoint: str, params: dict | None = None) -> dict:
        """Make a request to the MusicBrainz API."""
        params = params or {}
        params["fmt"] = "json"

        url = f"{MUSICBRAINZ_BASE_URL}{endpoint}"

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("MusicBrainz API request failed")
            raise

        return response.json()

    def search_releases(self, query: str, limit: int = 10) -> list[MusicBrainzResult]:
        """
        Search for music releases (albums).

        Args:
            query: The search query
            limit: Maximum number of results

        Returns:
            List of MusicBrainzResult objects
        """
        if not query or len(query) < MIN_QUERY_LENGTH:
            return []

        data = self._request("release", {"query": query, "limit": limit})

        return [
            MusicBrainzResult(
                mbid=release.get("id", ""),
                title=release.get("title", ""),
                artists=_extract_artists(release),
                year=_extract_year(release.get("date", "")),
                country=release.get("country"),
                label=_extract_label(release.get("label-info", [])),
            )
            for release in data.get("releases", [])
        ]

    def get_release_details(self, mbid: str) -> dict:
        """
        Get detailed information about a release (album).

        Args:
            mbid: The MusicBrainz release ID

        Returns a dict with:
            - title, year, overview
            - artists: list of artist names
            - genres: list of genre/tag names
            - cover_url: full URL for cover image
            - musicbrainz_url: URL to MusicBrainz page
            - media_type: "music"
        """
        data = self._request(f"release/{mbid}", {"inc": "artists+labels+tags+genres+release-groups"})

        artists = _extract_artists(data)
        year = _extract_year(data.get("date", ""))
        genres = _extract_genres_and_tags(data)
        label = _extract_label(data.get("label-info", []))

        # Build overview/description
        overview_parts = []
        if label:
            overview_parts.append(f"Label: {label}")
        if country := data.get("country"):
            overview_parts.append(f"Country: {country}")
        if primary_type := data.get("release-group", {}).get("primary-type"):
            overview_parts.append(f"Type: {primary_type}")

        return {
            "title": data.get("title", ""),
            "year": year,
            "overview": " | ".join(overview_parts) if overview_parts else "",
            "artists": artists,
            "contributors": artists,
            "genres": genres,
            "cover_url": f"{COVERART_BASE_URL}release/{mbid}/front-500",
            "musicbrainz_url": f"https://musicbrainz.org/release/{mbid}",
            "media_type": "music",
        }

    def check_cover_exists(self, mbid: str) -> bool:
        """
        Check if a cover exists in the Cover Art Archive.

        Args:
            mbid: The MusicBrainz release ID

        Returns:
            True if cover exists, False otherwise
        """
        try:
            response = self.session.head(
                f"{COVERART_BASE_URL}release/{mbid}/front",
                timeout=5,
                allow_redirects=True,
            )
        except requests.RequestException:
            return False
        return response.status_code == HTTPStatus.OK

    def download_cover(self, cover_url: str) -> bytes | None:
        """Download cover image and return bytes."""
        if not cover_url:
            return None

        # Basic validation - ensure it's from Cover Art Archive
        if not COVERART_PATTERN.match(cover_url):
            logger.warning("Invalid Cover Art Archive URL: %s", cover_url)
            return None

        try:
            response = self.session.get(cover_url, timeout=15, allow_redirects=True)
            # Cover Art Archive returns 404 if no cover exists
            if response.status_code == HTTPStatus.NOT_FOUND:
                logger.info("No cover art available for: %s", cover_url)
                return None
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Failed to download cover from %s", cover_url)
            return None

        # Check minimum size
        if len(response.content) < MIN_COVER_SIZE_BYTES:
            logger.warning("Cover too small (placeholder?): %s", cover_url)
            return None

        return response.content


def get_musicbrainz_client() -> MusicBrainzClient:
    """
    Factory function to get a MusicBrainz client instance.

    MusicBrainz doesn't require authentication, so this always returns a client.
    """
    return MusicBrainzClient()
