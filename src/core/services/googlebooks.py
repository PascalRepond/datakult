"""
Google Books API client for fetching book metadata.

API Documentation: https://developers.google.com/books/docs/v1/using
"""

import html
import logging
import re
from dataclasses import dataclass
from urllib.parse import quote, urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

GOOGLEBOOKS_BASE_URL = "https://www.googleapis.com/books/v1/"

MIN_QUERY_LENGTH = 2

# Pattern for valid Google Books cover URLs — our URL builders always emit https
GOOGLEBOOKS_COVER_PATTERN = re.compile(r"^https://books\.google\.com/books/(?:content|publisher/content)[?/][^\s]+$")

# Minimum size in bytes to consider a cover valid
MIN_COVER_SIZE_BYTES = 1000


def _strip_html(text: str) -> str:
    """Strip HTML tags and decode entities from a description."""
    if not text:
        return ""
    # Replace block-level tags with newlines for readability
    text = re.sub(r"<\s*(br|p|/p|/div)\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def _extract_year(published_date: str) -> int | None:
    """Extract year from Google Books publishedDate (YYYY, YYYY-MM, or YYYY-MM-DD)."""
    if not published_date:
        return None
    match = re.match(r"(\d{4})", published_date)
    return int(match.group(1)) if match else None


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
    # Replace any zoom=N with the fife hint; if no zoom is present, append it
    if re.search(r"[?&]zoom=\d+", rewritten):
        rewritten = re.sub(r"([?&])zoom=\d+", rf"\g<1>fife={fife}", rewritten)
    else:
        separator = "&" if "?" in rewritten else "?"
        rewritten = f"{rewritten}{separator}fife={fife}"
    return rewritten


@dataclass
class GoogleBooksResult:
    """Represents a search result from Google Books."""

    volume_id: str
    title: str
    authors: list[str]
    year: int | None
    thumbnail_url: str | None

    source: str = "googlebooks"

    @property
    def cover_url(self) -> str | None:
        """Returns the cover URL sized for the import flow (~800x1200)."""
        return _resize_cover_url(self.thumbnail_url, "w800-h1200") if self.thumbnail_url else None

    @property
    def cover_url_small(self) -> str | None:
        """Returns a small cover URL for search result thumbnails (~128x192)."""
        return _resize_cover_url(self.thumbnail_url, "w128-h192") if self.thumbnail_url else None

    @property
    def cover_url_large(self) -> str | None:
        """Returns the larger cover URL (same as cover_url — downloads are compressed to 800 anyway)."""
        return self.cover_url


class GoogleBooksClient:
    """Client for interacting with the Google Books API."""

    def __init__(self):
        # Google Books frequently returns transient 5xx errors (especially 503
        # "backendFailed") even on valid queries. Retry a couple of times with
        # small backoff before giving up.
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.4,
            status_forcelist=(500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _request(self, endpoint: str, params: dict | None = None) -> dict:
        """Make a request to the Google Books API."""
        params = params or {}
        url = f"{GOOGLEBOOKS_BASE_URL}{endpoint}"
        if params:
            url = f"{url}?{urlencode(params)}"

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Google Books API request failed")
            raise

        return response.json()

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

        data = self._request(
            "volumes",
            {
                "q": query,
                "maxResults": min(limit, 40),
                "printType": "books",
                "projection": "lite",
            },
        )

        results = []
        for item in data.get("items", []):
            volume_info = item.get("volumeInfo", {})
            image_links = volume_info.get("imageLinks", {})
            thumbnail = image_links.get("thumbnail") or image_links.get("smallThumbnail")

            results.append(
                GoogleBooksResult(
                    volume_id=item.get("id", ""),
                    title=volume_info.get("title", ""),
                    authors=volume_info.get("authors", []),
                    year=_extract_year(volume_info.get("publishedDate", "")),
                    thumbnail_url=thumbnail,
                )
            )

        return results

    def get_volume_details(self, volume_id: str) -> dict:
        """
        Get detailed information about a volume (book).

        Returns a dict shaped like the other services for the import flow:
            - title, year, overview (description)
            - authors: list of author names
            - contributors: same as authors (for form pre-fill)
            - genres: list of categories (for tag pre-fill)
            - cover_url: full URL for cover image
            - googlebooks_url: URL to the Google Books page
            - media_type: "book"
        """
        data = self._request(f"volumes/{quote(volume_id, safe='')}")
        volume_info = data.get("volumeInfo", {})

        title = volume_info.get("title", "")
        if subtitle := volume_info.get("subtitle"):
            title = f"{title}: {subtitle}"

        authors = volume_info.get("authors", [])
        year = _extract_year(volume_info.get("publishedDate", ""))
        overview = _strip_html(volume_info.get("description", ""))
        categories = volume_info.get("categories", [])

        image_links = volume_info.get("imageLinks", {})
        thumbnail = image_links.get("thumbnail") or image_links.get("smallThumbnail")
        cover_url = _resize_cover_url(thumbnail, "w800-h1200") if thumbnail else None

        # canonicalLink is not always present; info_link is a reliable fallback
        googlebooks_url = volume_info.get("canonicalVolumeLink") or volume_info.get(
            "infoLink", f"https://books.google.com/books?id={volume_id}"
        )

        return {
            "title": title,
            "year": year,
            "overview": overview,
            "authors": authors,
            "contributors": authors,
            "genres": categories,
            "cover_url": cover_url,
            "googlebooks_url": googlebooks_url,
            "media_type": "book",
        }

    def download_cover(self, cover_url: str) -> bytes | None:
        """Download cover image and return bytes."""
        if not cover_url:
            return None

        if not GOOGLEBOOKS_COVER_PATTERN.match(cover_url):
            logger.warning("Invalid Google Books cover URL: %s", cover_url)
            return None

        try:
            response = self.session.get(cover_url, timeout=15)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Failed to download cover from %s", cover_url)
            return None

        if len(response.content) < MIN_COVER_SIZE_BYTES:
            logger.warning("Cover not available (placeholder returned): %s", cover_url)
            return None

        return response.content


def get_googlebooks_client() -> GoogleBooksClient:
    """
    Factory function to get a Google Books client instance.

    Google Books doesn't require authentication for searches, so this always returns a client.
    """
    return GoogleBooksClient()
