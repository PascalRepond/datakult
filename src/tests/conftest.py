"""
Fixtures for Datakult tests.

This file contains shared fixtures available to all test modules.
See https://docs.pytest.org/en/stable/reference/fixtures.html
"""

import pytest
import requests
from django.utils import translation


@pytest.fixture(autouse=True)
def _reset_language():
    """Deactivate the language that a test request activated, so that it does not leak into the next tests."""
    yield
    translation.deactivate()


@pytest.fixture(autouse=True)
def _isolate_media_root(settings, tmp_path):
    """Store media files in a temporary directory, so that tests neither read nor write the real media files."""
    settings.MEDIA_ROOT = tmp_path


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
def agent(db):
    """Create and return a sample Agent instance."""
    from core.models import Agent

    return Agent.objects.create(name="Test Author")


@pytest.fixture
def media(db, agent):
    """Create and return a sample Media instance with an agent."""
    from core.models import Media

    media = Media.objects.create(
        title="Test Media",
        media_type="BOOK",
        status="PLANNED",
        pub_year=2024,
    )
    media.contributors.add(agent)
    return media


@pytest.fixture
def media_factory(db):
    """Factory fixture to create multiple Media instances."""

    def create_media(**kwargs):
        from core.models import Media

        defaults = {
            "title": "Default Title",
            "media_type": "BOOK",
            "status": "PLANNED",
        }
        defaults.update(kwargs)
        return Media.objects.create(**defaults)

    return create_media


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
def logged_in_client(client, user):
    """Return a client with an authenticated user."""
    client.force_login(user)
    return client


@pytest.fixture
def cover_png():
    """Return the bytes of a dark grey (#333333) PNG cover."""
    from io import BytesIO

    from PIL import Image

    output = BytesIO()
    Image.new("RGB", (400, 600), color="#333333").save(output, format="PNG")
    return output.getvalue()
