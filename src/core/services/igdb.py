"""
IGDB API client for fetching video game metadata.

API Documentation: https://api-docs.igdb.com/
Authentication: Uses Twitch OAuth2 - https://dev.twitch.tv/docs/authentication/

To use this API, you need to:
1. Create an application at https://dev.twitch.tv/console
2. Set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET in your environment
"""

import datetime
import logging
import time
from dataclasses import dataclass

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

IGDB_BASE_URL = "https://api.igdb.com/v4/"
TWITCH_AUTH_URL = "https://id.twitch.tv/oauth2/token"
IGDB_IMAGE_BASE_URL = "https://images.igdb.com/igdb/image/upload/"

# Minimum query length for search
MIN_QUERY_LENGTH = 2

# Cache for access token (simple in-memory cache)
_token_cache: dict = {"access_token": None, "expires_at": 0}


class IGDBError(Exception):
    """Exception raised when IGDB API credentials are missing or invalid."""


@dataclass
class IGDBResult:
    """Represents a search result from IGDB."""

    igdb_id: int
    name: str
    year: int | None
    summary: str
    cover_url: str | None
    cover_url_small: str | None


def _get_image_url(image_id: str | None, size: str = "cover_big") -> str | None:
    """
    Build IGDB image URL from image ID.

    Size options: cover_small (90x128), cover_big (264x374),
                  screenshot_med (569x320), 720p, 1080p
    """
    if not image_id:
        return None
    return f"{IGDB_IMAGE_BASE_URL}t_{size}/{image_id}.jpg"


def _escape_apicalypse_query(query: str) -> str:
    """Escape user input for Apicalypse queries."""
    return query.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()


class IGDBClient:
    """Client for interacting with the IGDB API."""

    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        self.client_id = client_id or getattr(settings, "TWITCH_CLIENT_ID", "")
        self.client_secret = client_secret or getattr(settings, "TWITCH_CLIENT_SECRET", "")

        if not self.client_id or not self.client_secret:
            msg = "TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET are required."
            raise IGDBError(msg)

    def _get_access_token(self) -> str:
        """
        Get a valid access token, refreshing if necessary.

        Uses Twitch's client credentials flow.
        """
        # Check if cached token is still valid (with 60s buffer)
        if _token_cache["access_token"] and _token_cache["expires_at"] > time.time() + 60:
            return _token_cache["access_token"]

        # Request new token
        try:
            response = requests.post(
                TWITCH_AUTH_URL,
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            _token_cache["access_token"] = data["access_token"]
            _token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)

        except requests.RequestException as e:
            logger.exception("Failed to get Twitch access token")
            msg = "Failed to authenticate with Twitch"
            raise IGDBError(msg) from e

        return _token_cache["access_token"]

    def _request(self, endpoint: str, body: str) -> list[dict]:
        """
        Make a request to the IGDB API.

        IGDB uses POST requests with a custom query language (Apicalypse).
        """
        access_token = self._get_access_token()

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "text/plain",
        }

        url = f"{IGDB_BASE_URL}{endpoint}"

        try:
            response = requests.post(url, headers=headers, data=body, timeout=10)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("IGDB API request failed")
            raise

        return response.json()

    def search_games(self, query: str, limit: int = 10) -> list[IGDBResult]:
        """
        Search for video games.

        Args:
            query: The search query
            limit: Maximum number of results

        Returns:
            List of IGDBResult objects
        """
        if not query or len(query) < MIN_QUERY_LENGTH:
            return []

        # Apicalypse query language
        # See: https://api-docs.igdb.com/#apicalypse
        safe_query = _escape_apicalypse_query(query)
        body = f"""
            search "{safe_query}";
            fields name, first_release_date, summary, cover.image_id;
            limit {limit};
        """

        data = self._request("games", body)

        results = []
        for item in data:
            # Extract year from Unix timestamp
            release_date = item.get("first_release_date")
            year = None
            if release_date:
                year = datetime.datetime.fromtimestamp(release_date, tz=datetime.UTC).year

            # Extract cover image ID
            cover = item.get("cover", {})
            cover_image_id = cover.get("image_id") if isinstance(cover, dict) else None

            results.append(
                IGDBResult(
                    igdb_id=item.get("id"),
                    name=item.get("name", ""),
                    year=year,
                    summary=item.get("summary", ""),
                    cover_url=_get_image_url(cover_image_id, "cover_big"),
                    cover_url_small=_get_image_url(cover_image_id, "cover_small"),
                )
            )

        return results

    def get_game_details(self, game_id: int) -> dict:
        """
        Get detailed information about a game.

        Returns a dict with:
            - name, year, summary
            - developers: list of developer names
            - publishers: list of publisher names
            - genres: list of genre names
            - cover_url: full URL for cover image
            - igdb_url: URL to IGDB page
        """
        body = f"""
            fields name, first_release_date, summary, url,
                   cover.image_id,
                   involved_companies.company.name, involved_companies.developer, involved_companies.publisher,
                   genres.name;
            where id = {game_id};
        """

        data = self._request("games", body)

        if not data:
            return {}

        game = data[0]

        # Extract year
        release_date = game.get("first_release_date")
        year = None
        if release_date:
            year = datetime.datetime.fromtimestamp(release_date, tz=datetime.UTC).year

        # Extract developers and publishers
        developers = []
        publishers = []
        for company_info in game.get("involved_companies", []):
            company = company_info.get("company", {})
            company_name = company.get("name") if isinstance(company, dict) else None
            if company_name:
                if company_info.get("developer"):
                    developers.append(company_name)
                if company_info.get("publisher"):
                    publishers.append(company_name)

        # Extract genres
        genres = [g.get("name") for g in game.get("genres", []) if g.get("name")]

        # Extract cover
        cover = game.get("cover", {})
        cover_image_id = cover.get("image_id") if isinstance(cover, dict) else None

        return {
            "title": game.get("name", ""),
            "year": year,
            "overview": game.get("summary", ""),
            "developers": developers,
            "publishers": publishers,
            "contributors": developers,  # Use developers as primary contributors
            "genres": genres,
            "cover_url": _get_image_url(cover_image_id, "cover_big"),
            "igdb_url": game.get("url", f"https://www.igdb.com/games/{game_id}"),
            "media_type": "game",
        }

    def download_cover(self, cover_url: str) -> bytes | None:
        """Download cover image and return bytes."""
        if not cover_url:
            return None

        # Basic validation - ensure it's from IGDB
        if not cover_url.startswith(IGDB_IMAGE_BASE_URL):
            logger.warning("Invalid IGDB cover URL: %s", cover_url)
            return None

        try:
            response = requests.get(cover_url, timeout=15)
            response.raise_for_status()
        except requests.RequestException:
            logger.exception("Failed to download cover from %s", cover_url)
            return None

        return response.content


def get_igdb_client() -> IGDBClient | None:
    """
    Factory function to get an IGDB client instance.

    Returns None if the API credentials are not configured.
    """
    client_id = getattr(settings, "TWITCH_CLIENT_ID", "")
    client_secret = getattr(settings, "TWITCH_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        logger.warning("IGDB API credentials not configured")
        return None

    return IGDBClient()
