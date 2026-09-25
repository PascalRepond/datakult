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
import re
import time
from dataclasses import dataclass

from django.conf import settings

from .base import MIN_QUERY_LENGTH, APIClient, APIError

logger = logging.getLogger(__name__)

IGDB_BASE_URL = "https://api.igdb.com/v4/"
TWITCH_AUTH_URL = "https://id.twitch.tv/oauth2/token"
IGDB_IMAGE_BASE_URL = "https://images.igdb.com/igdb/image/upload/"

# Cache for access token (simple in-memory cache)
_token_cache: dict = {"access_token": None, "expires_at": 0}


class IGDBError(APIError):
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
    return f"{IGDB_IMAGE_BASE_URL}t_{size}/{image_id}.jpg" if image_id else None


def _cover_image_id(game: dict) -> str | None:
    """Return the image ID of the cover of a game, if it has one."""
    cover = game.get("cover", {})
    return cover.get("image_id") if isinstance(cover, dict) else None


def _release_year(game: dict) -> int | None:
    """Return the year of the first release of a game, given as a Unix timestamp."""
    timestamp = game.get("first_release_date")
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.UTC).year if timestamp else None


def _company_name(company_info: dict) -> str | None:
    """Return the name of the company involved in a game."""
    company = company_info.get("company", {})
    return company.get("name") if isinstance(company, dict) else None


def _escape_apicalypse_query(query: str) -> str:
    """Escape user input for Apicalypse queries."""
    return query.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").strip()


class IGDBClient(APIClient):
    """Client for interacting with the IGDB API."""

    source_name = "IGDB"
    cover_url_pattern = re.compile(re.escape(IGDB_IMAGE_BASE_URL))

    def __init__(self, client_id: str | None = None, client_secret: str | None = None):
        super().__init__()
        self.client_id = client_id or settings.TWITCH_CLIENT_ID
        self.client_secret = client_secret or settings.TWITCH_CLIENT_SECRET

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

        try:
            data = self._request(
                TWITCH_AUTH_URL,
                method="POST",
                params={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
            )
        except APIError as e:
            msg = "Failed to authenticate with Twitch"
            raise IGDBError(msg) from e
        if "access_token" not in data:
            msg = "Twitch gave no access token"
            raise IGDBError(msg)

        _token_cache["access_token"] = data["access_token"]
        _token_cache["expires_at"] = time.time() + data.get("expires_in", 3600)
        return _token_cache["access_token"]

    def _query(self, endpoint: str, body: str) -> list[dict]:
        """
        Make a request to the IGDB API.

        IGDB uses POST requests with a custom query language (Apicalypse).
        """
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self._get_access_token()}",
            "Content-Type": "text/plain",
        }
        return self._request(f"{IGDB_BASE_URL}{endpoint}", method="POST", headers=headers, data=body)

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

        return [
            IGDBResult(
                igdb_id=item.get("id"),
                name=item.get("name", ""),
                year=_release_year(item),
                summary=item.get("summary", ""),
                cover_url=_get_image_url(_cover_image_id(item), "cover_big"),
                cover_url_small=_get_image_url(_cover_image_id(item), "cover_small"),
            )
            for item in self._query("games", body)
        ]

    def get_game_details(self, game_id: int) -> dict:
        """
        Get detailed information about a game.

        Returns a dict with:
            - title, year
            - contributors: list of developer names
            - genres: list of genre names
            - cover_url: full URL for cover image
            - source_url: URL to IGDB page
            - media_type: "game"
        """
        body = f"""
            fields name, first_release_date, summary, url,
                   cover.image_id,
                   involved_companies.company.name, involved_companies.developer,
                   genres.name;
            where id = {game_id};
        """

        data = self._query("games", body)

        if not data:
            return {}

        game = data[0]
        return {
            "title": game.get("name", ""),
            "year": _release_year(game),
            "contributors": [
                name
                for company_info in game.get("involved_companies", [])
                if company_info.get("developer") and (name := _company_name(company_info))
            ],
            "genres": [g.get("name") for g in game.get("genres", []) if g.get("name")],
            "cover_url": _get_image_url(_cover_image_id(game), "cover_big"),
            "source_url": game.get("url", f"https://www.igdb.com/games/{game_id}"),
            "media_type": "game",
        }


def get_igdb_client() -> IGDBClient | None:
    """
    Factory function to get an IGDB client instance.

    Returns None if the API credentials are not configured.
    """
    if not settings.TWITCH_CLIENT_ID or not settings.TWITCH_CLIENT_SECRET:
        logger.warning("IGDB API credentials not configured")
        return None

    return IGDBClient()
