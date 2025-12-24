"""
Tests for core.models module.

These tests verify custom behavior of the Agent and Media models.
Only application-specific logic is tested here, not Django ORM basics.
"""

import pytest
from django.core.exceptions import ValidationError

from core.models import Media


class TestAgentModel:
    """Tests for the Agent model."""

    def test_agent_str_representation(self, agent):
        """The string representation of an agent is its name."""
        assert str(agent) == agent.name


class TestMediaModel:
    """Tests for the Media model."""

    def test_media_str_representation(self, media):
        """The string representation of a media is its title."""
        assert str(media) == media.title

    def test_media_pub_year_validation_too_early(self, db):
        """Publication year before -4000 is rejected."""
        media = Media(
            title="Ancient Work",
            media_type="BOOK",
            pub_year=-5000,
        )

        with pytest.raises(ValidationError) as exc_info:
            media.full_clean()
        assert "pub_year" in exc_info.value.message_dict

    def test_media_pub_year_validation_too_late(self, db):
        """Publication year after 2200 is rejected."""
        media = Media(
            title="Future Work",
            media_type="BOOK",
            pub_year=2500,
        )

        with pytest.raises(ValidationError) as exc_info:
            media.full_clean()
        assert "pub_year" in exc_info.value.message_dict

    def test_media_pub_year_validation_valid_range(self, db):
        """Publication year within valid range is accepted."""
        media = Media(
            title="Normal Work",
            media_type="BOOK",
            pub_year=2024,
        )
        # Should not raise
        media.full_clean()
