"""
Fixtures for core app tests.

This file contains fixtures specific to the core application.
See https://docs.pytest.org/en/stable/reference/fixtures.html
"""

import pytest


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
