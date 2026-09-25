"""
Fixtures for Datakult tests.

This file contains shared fixtures available to all test modules.
See https://docs.pytest.org/en/stable/reference/fixtures.html
"""

import pytest
from django.utils import translation


@pytest.fixture(autouse=True)
def _reset_language():
    """Deactivate the language that a test request activated, so that it does not leak into the next tests."""
    yield
    translation.deactivate()


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
def cover_png(settings, tmp_path):
    """Return the bytes of a dark grey (#333333) PNG cover, storing media files in a temporary directory."""
    from io import BytesIO

    from PIL import Image

    settings.MEDIA_ROOT = tmp_path
    output = BytesIO()
    Image.new("RGB", (400, 600), color="#333333").save(output, format="PNG")
    return output.getvalue()
