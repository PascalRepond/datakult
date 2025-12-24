"""
Tests for core.models module.

These tests verify the behavior of the Agent and Media models.
"""

import pytest
from django.core.exceptions import ValidationError

from core.models import Agent, Media


class TestAgentModel:
    """Tests for the Agent model."""

    def test_agent_creation(self, db):
        """An agent can be created with a name."""
        agent = Agent.objects.create(name="John Doe")

        assert agent.name == "John Doe"
        assert agent.pk is not None

    def test_agent_str_representation(self, agent):
        """The string representation of an agent is its name."""
        assert str(agent) == agent.name

    def test_agent_created_at_is_set(self, agent):
        """The created_at field is automatically set."""
        assert agent.created_at is not None


class TestMediaModel:
    """Tests for the Media model."""

    def test_media_creation(self, db):
        """A media item can be created with required fields."""
        media = Media.objects.create(
            title="Test Book",
            media_type="BOOK",
            status="PLANNED",
        )

        assert media.title == "Test Book"
        assert media.media_type == "BOOK"
        assert media.status == "PLANNED"
        assert media.pk is not None

    def test_media_str_representation(self, media):
        """The string representation of a media is its title."""
        assert str(media) == media.title

    def test_media_default_status(self, db):
        """The default status of a media is PLANNED."""
        media = Media.objects.create(
            title="New Media",
            media_type="FILM",
        )

        assert media.status == "PLANNED"

    def test_media_can_have_contributors(self, media, agent):
        """A media can have contributors (agents)."""
        assert agent in media.contributors.all()

    def test_media_pub_year_validation(self, db):
        """Publication year must be within valid range."""
        media = Media(
            title="Ancient Work",
            media_type="BOOK",
            pub_year=-5000,  # Before -4000 limit
        )

        with pytest.raises(ValidationError):
            media.full_clean()

    def test_media_score_choices(self, db):
        """Score must be between 1 and 10."""
        media = Media.objects.create(
            title="Rated Media",
            media_type="FILM",
            score=8,
        )

        assert media.score == 8

    def test_media_optional_fields(self, db):
        """Optional fields can be null or blank."""
        media = Media.objects.create(
            title="Minimal Media",
            media_type="GAME",
        )

        assert media.pub_year is None
        assert media.score is None
        assert media.review == ""
        assert not media.cover  # ImageField is falsy when empty
