"""
OpenLibrary API client for fetching book metadata.

API Documentation: https://openlibrary.org/developers/api

This API is free and does not require authentication.
Rate limiting: Please be respectful and limit requests to ~1/second.
"""

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlencode, urljoin

import requests

logger = logging.getLogger(__name__)

OPENLIBRARY_BASE_URL = "https://openlibrary.org/"
OPENLIBRARY_COVERS_URL = "https://covers.openlibrary.org/"

# Minimum query length for search
MIN_QUERY_LENGTH = 2

# Pattern for valid OpenLibrary cover URLs
OPENLIBRARY_COVER_PATTERN = re.compile(r"^https://covers\.openlibrary\.org/[baw]/(?:id|olid|isbn)/[^/]+\.jpg$")

# Minimum size in bytes to consider a cover valid (OpenLibrary returns 1x1 pixel placeholder)
MIN_COVER_SIZE_BYTES = 1000


class OpenLibraryError(Exception):
    """Exception raised when OpenLibrary API request fails."""


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
        if self.cover_id:
            return f"{OPENLIBRARY_COVERS_URL}b/id/{self.cover_id}-M.jpg"
        return None

    @property
    def cover_url_small(self) -> str | None:
        """Returns a smaller cover URL for thumbnails."""
        if self.cover_id:
            return f"{OPENLIBRARY_COVERS_URL}b/id/{self.cover_id}-S.jpg"
        return None

    @property
    def cover_url_large(self) -> str | None:
        """Returns a larger cover URL."""
        if self.cover_id:
            return f"{OPENLIBRARY_COVERS_URL}b/id/{self.cover_id}-L.jpg"
        return None


class OpenLibraryClient:
    """Client for interacting with the OpenLibrary API."""

    def __init__(self):
        # OpenLibrary doesn't require authentication
        pass

    def _request(self, endpoint: str, params: dict | None = None) -> dict:
        """Make a request to the OpenLibrary API."""
        params = params or {}

        url = urljoin(OPENLIBRARY_BASE_URL, endpoint)
        if params:
            url = f"{url}?{urlencode(params)}"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("OpenLibrary API request failed")
            raise

        return response.json()

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

        data = self._request(
            "search.json",
            {
                "q": query,
                "limit": limit,
                "fields": "key,title,author_name,first_publish_year,cover_i",
            },
        )

        results = []
        for doc in data.get("docs", []):
            # Get first cover ID if available
            cover_id = doc.get("cover_i")

            # Get authors list
            authors = doc.get("author_name", [])

            results.append(
                OpenLibraryResult(
                    work_key=doc.get("key", ""),
                    title=doc.get("title", ""),
                    authors=authors if isinstance(authors, list) else [authors],
                    year=doc.get("first_publish_year"),
                    cover_id=cover_id,
                )
            )

        return results

    def get_work_details(self, work_key: str, first_publish_year: int | None = None) -> dict:
        """
        Get detailed information about a work (book).

        Args:
            work_key: The work key (e.g., "/works/OL45883W" or just "OL45883W")
            first_publish_year: Optional year from search results

        Returns a dict with:
            - title, year, overview (description)
            - authors: list of author names
            - cover_url: full URL for cover image
            - openlibrary_url: URL to OpenLibrary page
        """
        # Normalize work key
        if not work_key.startswith("/works/"):
            work_key = f"/works/{work_key}"

        # Fetch work details
        work_data = self._request(f"{work_key}.json")

        # Extract description
        description = work_data.get("description", "")
        if isinstance(description, dict):
            description = description.get("value", "")

        # Get cover IDs
        cover_ids = work_data.get("covers", [])
        cover_id = cover_ids[0] if cover_ids else None
        cover_url = f"{OPENLIBRARY_COVERS_URL}b/id/{cover_id}-L.jpg" if cover_id else None

        # Get authors - need to fetch each author
        authors = []
        for author_ref in work_data.get("authors", []):
            author_key = None
            if isinstance(author_ref, dict):
                # Can be {"author": {"key": "/authors/..."}} or {"key": "/authors/..."}
                author_key = author_ref["author"].get("key") if "author" in author_ref else author_ref.get("key")

            if author_key:
                try:
                    author_data = self._request(f"{author_key}.json")
                    if author_data.get("name"):
                        authors.append(author_data["name"])
                except requests.RequestException:
                    logger.warning("Failed to fetch author: %s", author_key)

        return {
            "title": work_data.get("title", ""),
            "year": first_publish_year,
            "overview": description,
            "authors": authors,
            "contributors": authors,
            "cover_url": cover_url,
            "openlibrary_url": f"https://openlibrary.org{work_key}",
            "media_type": "book",
        }

    def get_book_by_isbn(self, isbn: str) -> dict | None:
        """
        Get book details by ISBN.

        Args:
            isbn: ISBN-10 or ISBN-13

        Returns:
            Book details dict or None if not found
        """
        # Clean ISBN (remove dashes and spaces)
        isbn = re.sub(r"[\s-]", "", isbn)

        try:
            data = self._request(f"isbn/{isbn}.json")
        except requests.RequestException:
            return None

        if not data:
            return None

        # ISBN endpoint returns an edition, get the work for full details
        works = data.get("works", [])
        if works:
            work_key = works[0].get("key")
            if work_key:
                details = self.get_work_details(work_key)
                # Override year with edition's publish date if available
                publish_date = data.get("publish_date", "")
                if publish_date:
                    # Try to extract year from various date formats
                    year_match = re.search(r"\b(1[89]\d{2}|20[0-2]\d)\b", publish_date)
                    if year_match:
                        details["year"] = int(year_match.group(1))
                return details

        return None

    def download_cover(self, cover_url: str) -> bytes | None:
        """Download cover image and return bytes."""
        if not cover_url:
            return None

        # Basic validation - ensure it's from OpenLibrary
        if not OPENLIBRARY_COVER_PATTERN.match(cover_url):
            logger.warning("Invalid OpenLibrary cover URL: %s", cover_url)
            return None

        try:
            response = requests.get(cover_url, timeout=15)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Failed to download cover from %s", cover_url)
            return None

        # OpenLibrary returns a 1x1 pixel if cover doesn't exist
        if len(response.content) < MIN_COVER_SIZE_BYTES:
            logger.warning("Cover not available (placeholder returned): %s", cover_url)
            return None

        return response.content


def get_openlibrary_client() -> OpenLibraryClient:
    """
    Factory function to get an OpenLibrary client instance.

    OpenLibrary doesn't require authentication, so this always returns a client.
    """
    return OpenLibraryClient()
