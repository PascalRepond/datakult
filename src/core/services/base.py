"""Shared behaviour of the clients of the external metadata sources: their requests and cover downloads."""

import logging
import re
from http import HTTPStatus
from urllib.parse import urlsplit

import requests

logger = logging.getLogger(__name__)

API_TIMEOUT = 10  # seconds
COVER_TIMEOUT = 15  # seconds
# Queries shorter than this are not searched
MIN_QUERY_LENGTH = 2
# Size under which a cover is the placeholder that some sources return for a missing cover, in bytes
MIN_COVER_SIZE_BYTES = 1000


class APIError(Exception):
    """A metadata source cannot be used."""


def extract_year(date: str | None) -> int | None:
    """Return the year leading a date (YYYY, YYYY-MM or YYYY-MM-DD), or None without one."""
    match = re.match(r"(\d{4})", date or "")
    return int(match[1]) if match else None


class APIClient:
    """Base client of a metadata source."""

    source_name: str  # Named in the logs
    cover_url_pattern: re.Pattern  # Covers are only downloaded from the image server of the source
    min_cover_size = 0  # Smaller files are placeholders, for the sources that return one for a missing cover

    def __init__(self):
        self.session = requests.Session()

    def _request(self, url: str, method: str = "GET", **kwargs):
        """Send a request to the API of the source, and return its JSON response, or raise an APIError."""
        try:
            response = self.session.request(method, url, timeout=API_TIMEOUT, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as error:
            # The error would pass on the full URL, and so the API key its query may hold: only its path is told
            reason = error.response.status_code if error.response is not None else type(error).__name__
            message = f"{self.source_name} request to {urlsplit(url).path} failed: {reason}"
            logger.warning(message)
            raise APIError(message) from None

    def download_cover(self, cover_url: str) -> bytes | None:
        """Download a cover from the source, and return its bytes, or None when there is none."""
        if not cover_url:
            return None

        if not self.cover_url_pattern.match(cover_url):
            logger.warning("Invalid %s cover URL: %s", self.source_name, cover_url)
            return None

        try:
            response = self.session.get(cover_url, timeout=COVER_TIMEOUT)
            if response.status_code == HTTPStatus.NOT_FOUND:
                logger.info("No cover available for: %s", cover_url)
                return None
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Failed to download cover from %s", cover_url)
            return None

        if len(response.content) < self.min_cover_size:
            logger.warning("Cover not available (placeholder returned): %s", cover_url)
            return None

        return response.content
