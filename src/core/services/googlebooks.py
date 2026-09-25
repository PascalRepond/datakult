"""
Google Books API client for fetching book metadata.

API Documentation: https://developers.google.com/books/docs/v1/using
"""

import logging
import re
from dataclasses import dataclass
from urllib.parse import quote

from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .base import MIN_COVER_SIZE_BYTES, MIN_QUERY_LENGTH, APIClient, extract_year

logger = logging.getLogger(__name__)

GOOGLEBOOKS_BASE_URL = "https://www.googleapis.com/books/v1/"

# Pattern for valid Google Books cover URLs — our URL builders always emit https
GOOGLEBOOKS_COVER_PATTERN = re.compile(r"^https://books\.google\.com/books/(?:content|publisher/content)[?/][^\s]+$")


def _resize_cover_url(url: str, fife: str) -> str:
    """
    Rewrite a Google Books thumbnail URL to request a specific output size.

    The `zoom` parameter on the default thumbnail only goes up to ~128x192
    (zoom=1) which is unusably small for covers. Google's image backend
    honours the `fife=wW-hH` hint (used across Google properties) to scale
    the same source image to an arbitrary bounding box.
    """
    if not url:
        return url
    # Force HTTPS and drop the page-curl overlay
    rewritten = url.replace("http://", "https://", 1).replace("&edge=curl", "").replace("edge=curl&", "")
    if re.search(r"[?&]zoom=\d+", rewritten):
        return re.sub(r"([?&])zoom=\d+", rf"\g<1>fife={fife}", rewritten)
    separator = "&" if "?" in rewritten else "?"
    return f"{rewritten}{separator}fife={fife}"


def _thumbnail(volume_info: dict) -> str | None:
    """Return the URL of the thumbnail of a volume, the one Google Books resizes into covers."""
    image_links = volume_info.get("imageLinks", {})
    return image_links.get("thumbnail") or image_links.get("smallThumbnail")


@dataclass
class GoogleBooksResult:
    """Represents a search result from Google Books."""

    volume_id: str
    title: str
    authors: list[str]
    year: int | None
    thumbnail_url: str | None

    @property
    def cover_url(self) -> str | None:
        """Returns the cover URL sized for the import flow (~800x1200)."""
        return _resize_cover_url(self.thumbnail_url, "w800-h1200") if self.thumbnail_url else None

    @property
    def cover_url_small(self) -> str | None:
        """Returns a small cover URL for search result thumbnails (~128x192)."""
        return _resize_cover_url(self.thumbnail_url, "w128-h192") if self.thumbnail_url else None


def _search_result(item: dict) -> GoogleBooksResult:
    """Return a volume found by a search."""
    volume_info = item.get("volumeInfo", {})
    return GoogleBooksResult(
        volume_id=item.get("id", ""),
        title=volume_info.get("title", ""),
        authors=volume_info.get("authors", []),
        year=extract_year(volume_info.get("publishedDate")),
        thumbnail_url=_thumbnail(volume_info),
    )


class GoogleBooksClient(APIClient):
    """Client for interacting with the Google Books API."""

    source_name = "Google Books"
    cover_url_pattern = GOOGLEBOOKS_COVER_PATTERN
    min_cover_size = MIN_COVER_SIZE_BYTES

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key
        # Google Books frequently returns transient 5xx errors (especially 503
        # "backendFailed") even on valid queries. Retry a couple of times with
        # small backoff before giving up.
        retry = Retry(
            total=3,
            backoff_factor=0.4,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """Make a request to the Google Books API."""
        # Google Books refuses anonymous requests, whose shared quota is exhausted
        params = {**(params or {}), "key": self.api_key} if self.api_key else params
        return self._request(f"{GOOGLEBOOKS_BASE_URL}{endpoint}", params=params)

    def search_books(self, query: str, limit: int = 10) -> list[GoogleBooksResult]:
        """
        Search for books.

        Args:
            query: The search query
            limit: Maximum number of results (Google Books allows up to 40)

        Returns:
            List of GoogleBooksResult objects
        """
        if not query or len(query) < MIN_QUERY_LENGTH:
            return []

        data = self._get(
            "volumes",
            {
                "q": query,
                "maxResults": min(limit, 40),
                "printType": "books",
                "projection": "lite",
            },
        )

        return [_search_result(item) for item in data.get("items", [])]

    def get_volume_details(self, volume_id: str) -> dict:
        """
        Get detailed information about a volume (book).

        Returns a dict shaped like the other services for the import flow:
            - title, year
            - contributors: list of author names
            - genres: list of categories (for tag pre-fill)
            - cover_url: full URL for cover image
            - source_url: URL to the Google Books page
            - media_type: "book"
        """
        volume_info = self._get(f"volumes/{quote(volume_id, safe='')}").get("volumeInfo", {})

        title = volume_info.get("title", "")
        if subtitle := volume_info.get("subtitle"):
            title = f"{title}: {subtitle}"
        thumbnail = _thumbnail(volume_info)

        return {
            "title": title,
            "year": extract_year(volume_info.get("publishedDate")),
            "contributors": volume_info.get("authors", []),
            "genres": volume_info.get("categories", []),
            "cover_url": _resize_cover_url(thumbnail, "w800-h1200") if thumbnail else None,
            # canonicalVolumeLink is not always present; infoLink is a reliable fallback
            "source_url": volume_info.get("canonicalVolumeLink")
            or volume_info.get("infoLink", f"https://books.google.com/books?id={volume_id}"),
            "media_type": "book",
        }


def get_googlebooks_client() -> GoogleBooksClient | None:
    """
    Factory function to get a Google Books client instance.

    Returns None if the API key is not configured, as Google Books refuses anonymous requests.
    """
    if not settings.GOOGLE_BOOKS_API_KEY:
        logger.warning("Google Books API key not configured")
        return None
    return GoogleBooksClient(api_key=settings.GOOGLE_BOOKS_API_KEY)
