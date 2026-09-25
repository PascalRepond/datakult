"""
MusicBrainz API client for fetching music album metadata.

API Documentation: https://musicbrainz.org/doc/MusicBrainz_API
Cover Art Archive: https://coverartarchive.org/

This API is free and does not require authentication.
Rate limiting: 1 request per second with a proper User-Agent header.
"""

import re
from dataclasses import dataclass
from urllib.parse import quote

from .base import MIN_COVER_SIZE_BYTES, MIN_QUERY_LENGTH, APIClient, extract_year

MUSICBRAINZ_BASE_URL = "https://musicbrainz.org/ws/2/"
COVERART_BASE_URL = "https://coverartarchive.org/"

# User-Agent is required by MusicBrainz API
USER_AGENT = "Datakult/1.0 (personal media tracker)"

# Pattern for valid Cover Art Archive URLs
COVERART_PATTERN = re.compile(r"^https://coverartarchive\.org/release/[a-f0-9-]+/")


def _extract_artists(data: dict) -> list[str]:
    """Extract artist names from artist-credit data."""
    return [ac["name"] for ac in data.get("artist-credit", []) if isinstance(ac, dict) and "name" in ac]


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


def _cover_url(mbid: str, size: str) -> str | None:
    """Return the URL of the front cover of a release, at one of the sizes of the Cover Art Archive."""
    return f"{COVERART_BASE_URL}release/{mbid}/{size}" if mbid else None


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
        return _cover_url(self.mbid, "front-500")

    @property
    def cover_url_small(self) -> str | None:
        """Returns a smaller cover URL for thumbnails (250px)."""
        return _cover_url(self.mbid, "front-250")


class MusicBrainzClient(APIClient):
    """Client for interacting with the MusicBrainz API."""

    source_name = "MusicBrainz"
    cover_url_pattern = COVERART_PATTERN
    min_cover_size = MIN_COVER_SIZE_BYTES

    def __init__(self):
        super().__init__()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            }
        )

    def _get(self, endpoint: str, params: dict) -> dict:
        """Make a request to the MusicBrainz API."""
        return self._request(f"{MUSICBRAINZ_BASE_URL}{endpoint}", params={**params, "fmt": "json"})

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

        data = self._get("release", {"query": query, "limit": limit})

        return [
            MusicBrainzResult(
                mbid=release.get("id", ""),
                title=release.get("title", ""),
                artists=_extract_artists(release),
                year=extract_year(release.get("date")),
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
            - title, year
            - contributors: list of artist names
            - genres: list of genre/tag names
            - cover_url: full URL for cover image
            - source_url: URL to MusicBrainz page
            - media_type: "music"
        """
        data = self._get(f"release/{quote(mbid, safe='')}", {"inc": "artists+labels+tags+genres+release-groups"})

        return {
            "title": data.get("title", ""),
            "year": extract_year(data.get("date")),
            "contributors": _extract_artists(data),
            "genres": _extract_genres_and_tags(data),
            "cover_url": _cover_url(mbid, "front-500"),
            "source_url": f"https://musicbrainz.org/release/{mbid}",
            "media_type": "music",
        }


def get_musicbrainz_client() -> MusicBrainzClient:
    """
    Factory function to get a MusicBrainz client instance.

    MusicBrainz doesn't require authentication, so this always returns a client.
    """
    return MusicBrainzClient()
