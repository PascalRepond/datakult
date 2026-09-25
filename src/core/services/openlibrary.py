"""
OpenLibrary API client for fetching book metadata.

API Documentation: https://openlibrary.org/developers/api

This API is free and does not require authentication.
Rate limiting: Please be respectful and limit requests to ~1/second.
"""

import logging
import re
from dataclasses import dataclass
from urllib.parse import quote, urljoin

from .base import MIN_COVER_SIZE_BYTES, MIN_QUERY_LENGTH, APIClient, APIError

logger = logging.getLogger(__name__)

OPENLIBRARY_BASE_URL = "https://openlibrary.org/"
OPENLIBRARY_COVERS_URL = "https://covers.openlibrary.org/"

# Pattern for valid OpenLibrary cover URLs
OPENLIBRARY_COVER_PATTERN = re.compile(r"^https://covers\.openlibrary\.org/[baw]/(?:id|olid|isbn)/[^/]+\.jpg$")


def _cover_url(cover_id: int | None, size: str) -> str | None:
    """Return the URL of a cover at one of the OpenLibrary sizes: S, M or L."""
    return f"{OPENLIBRARY_COVERS_URL}b/id/{cover_id}-{size}.jpg" if cover_id else None


def _author_names(doc: dict) -> list[str]:
    """Return the authors of a search result, which may be given as a single name."""
    authors = doc.get("author_name", [])
    return authors if isinstance(authors, list) else [authors]


@dataclass
class OpenLibraryResult:
    """Represents a search result from OpenLibrary."""

    work_key: str  # e.g., "/works/OL45883W"
    title: str
    authors: list[str]
    year: int | None
    cover_id: int | None

    @property
    def olid(self) -> str:
        """Extract the OpenLibrary ID from the work key."""
        return self.work_key.split("/")[-1] if self.work_key else ""

    @property
    def cover_url(self) -> str | None:
        """Returns the full URL for the cover image (medium size)."""
        return _cover_url(self.cover_id, "M")

    @property
    def cover_url_small(self) -> str | None:
        """Returns a smaller cover URL for thumbnails."""
        return _cover_url(self.cover_id, "S")


class OpenLibraryClient(APIClient):
    """Client for interacting with the OpenLibrary API, which requires no authentication."""

    source_name = "OpenLibrary"
    cover_url_pattern = OPENLIBRARY_COVER_PATTERN
    # OpenLibrary returns a 1x1 pixel placeholder for a missing cover
    min_cover_size = MIN_COVER_SIZE_BYTES

    def _get(self, endpoint: str, params: dict | None = None) -> dict:
        """Make a request to the OpenLibrary API."""
        return self._request(urljoin(OPENLIBRARY_BASE_URL, endpoint), params=params)

    def search_books(self, query: str, limit: int = 10) -> list[OpenLibraryResult]:
        """
        Search for books.

        Args:
            query: The search query
            limit: Maximum number of results

        Returns:
            List of OpenLibraryResult objects
        """
        if not query or len(query) < MIN_QUERY_LENGTH:
            return []

        data = self._get(
            "search.json",
            {
                "q": query,
                "limit": limit,
                "fields": "key,title,author_name,first_publish_year,cover_i",
            },
        )

        return [
            OpenLibraryResult(
                work_key=doc.get("key", ""),
                title=doc.get("title", ""),
                authors=_author_names(doc),
                year=doc.get("first_publish_year"),
                cover_id=doc.get("cover_i"),
            )
            for doc in data.get("docs", [])
        ]

    def get_work_details(self, work_key: str, first_publish_year: int | None = None) -> dict:
        """
        Get detailed information about a work (book).

        Args:
            work_key: The work key (e.g., "/works/OL45883W" or just "OL45883W")
            first_publish_year: Optional year from search results

        Returns a dict with:
            - title, year
            - contributors: list of author names
            - cover_url: full URL for cover image
            - source_url: URL to OpenLibrary page
            - media_type: "book"
        """
        # Normalize to a bare OLID and escape it — work_key is user-supplied
        olid = quote(work_key.removeprefix("/works/"), safe="")
        work_key = f"/works/{olid}"
        work_data = self._get(f"{work_key}.json")

        # Authors are only referenced by the work: each of them is fetched
        authors = []
        for author_ref in work_data.get("authors", []):
            author_key = None
            if isinstance(author_ref, dict):
                # Can be {"author": {"key": "/authors/..."}} or {"key": "/authors/..."}
                author_key = author_ref["author"].get("key") if "author" in author_ref else author_ref.get("key")

            if author_key:
                try:
                    author_data = self._get(f"{author_key}.json")
                    if author_data.get("name"):
                        authors.append(author_data["name"])
                except APIError:
                    logger.warning("Failed to fetch author: %s", author_key)

        cover_ids = work_data.get("covers", [])
        return {
            "title": work_data.get("title", ""),
            "year": first_publish_year,
            "contributors": authors,
            "cover_url": _cover_url(cover_ids[0] if cover_ids else None, "L"),
            "source_url": f"https://openlibrary.org{work_key}",
            "media_type": "book",
        }


def get_openlibrary_client() -> OpenLibraryClient:
    """
    Factory function to get an OpenLibrary client instance.

    OpenLibrary doesn't require authentication, so this always returns a client.
    """
    return OpenLibraryClient()
