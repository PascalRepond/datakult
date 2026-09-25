"""
Fixtures for Datakult tests.

This file contains shared fixtures available to all test modules.
See https://docs.pytest.org/en/stable/reference/fixtures.html
"""

import pytest
import requests
from django.utils import translation

from tests.helpers import image_bytes


@pytest.fixture(autouse=True)
def _reset_language():
    """Deactivate the language that a test request activated, so that it does not leak into the next tests."""
    yield
    translation.deactivate()


@pytest.fixture(autouse=True)
def _isolate_media_root(settings, tmp_path):
    """Store media files in a temporary directory, so that tests neither read nor write the real media files."""
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture(autouse=True)
def _fast_password_hasher(settings):
    """Hash passwords with a fast hasher, as the default one makes every created user cost a noticeable delay."""
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    """Fail any test that would reach an external API instead of mocking it."""

    def refuse(*args, **kwargs):
        msg = "Tests must not reach the network: mock the external API"
        raise RuntimeError(msg)

    monkeypatch.setattr(requests.Session, "request", refuse)


@pytest.fixture
def api_responses(monkeypatch, settings):
    """
    Answer the requests to the external APIs with the JSON set for their URL, without its query string.

    The API keys of the sources are set, so that every client can be created, and no Twitch token is cached yet.
    A URL without JSON cannot be reached.
    """
    from unittest.mock import MagicMock

    settings.TMDB_API_KEY = settings.GOOGLE_BOOKS_API_KEY = "key"
    settings.TWITCH_CLIENT_ID = settings.TWITCH_CLIENT_SECRET = "twitch"  # noqa: S105
    monkeypatch.setattr("core.services.igdb._token_cache", {"access_token": None, "expires_at": 0})
    responses = {}

    def respond(session, method, url, **kwargs):
        if (data := responses.get(url.split("?")[0])) is None:
            raise requests.ConnectionError(url)
        response = MagicMock(status_code=200)
        response.json.return_value = data
        return response

    monkeypatch.setattr(requests.Session, "request", respond)
    return responses


@pytest.fixture
def agent(db):
    """Create and return a sample Agent instance."""
    from core.models import Agent

    return Agent.objects.create(name="Test Author")


@pytest.fixture
def media_factory(db):
    """Factory fixture to create Media instances, with their contributors and tags."""

    def create_media(*, contributors=(), tags=(), **kwargs):
        from core.models import Media

        media = Media.objects.create(**{"title": "Default Title", "media_type": "BOOK", "status": "PLANNED", **kwargs})
        media.contributors.add(*contributors)
        media.tags.add(*tags)
        return media

    return create_media


@pytest.fixture
def media(media_factory, agent):
    """Create and return a sample Media instance with an agent."""
    return media_factory(title="Test Media", pub_year=2024, contributors=[agent])


@pytest.fixture
def user(db, django_user_model):
    """Create and return a test user."""
    return django_user_model.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        first_name="Test",
        last_name="User",
    )


@pytest.fixture
def other_user(db, django_user_model):
    """Create and return a user other than the test user."""
    return django_user_model.objects.create_user(username="otheruser", password="testpass123")


@pytest.fixture
def logged_in_client(client, user):
    """Return a client with an authenticated user."""
    client.force_login(user)
    return client


@pytest.fixture
def saved_view_factory(user):
    """Factory fixture to create saved views, of the test user unless told otherwise."""

    def create_saved_view(**kwargs):
        from core.models import SavedView

        return SavedView.objects.create(**{"user": user, "name": "View", **kwargs})

    return create_saved_view


@pytest.fixture
def cover_png():
    """Return the bytes of a dark grey (#333333) PNG cover."""
    return image_bytes((400, 600))
