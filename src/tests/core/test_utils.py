"""
Tests for core.utils module.

These tests verify the utility functions used by the application.
"""

from core.models import Agent, Media
from core.utils import delete_orphan_agents_by_ids


class TestDeleteOrphanAgentsByIds:
    """Tests for the delete_orphan_agents_by_ids function."""

    def test_deletes_orphan_agent(self, db):
        """An agent with no media is deleted."""
        orphan = Agent.objects.create(name="Orphan Agent")
        orphan_id = orphan.pk

        deleted_count = delete_orphan_agents_by_ids([orphan_id])

        assert deleted_count == 1
        assert not Agent.objects.filter(pk=orphan_id).exists()

    def test_keeps_agent_with_media(self, db):
        """An agent linked to a media is not deleted."""
        agent = Agent.objects.create(name="Active Agent")
        media = Media.objects.create(title="Test Media", media_type="BOOK")
        media.contributors.add(agent)

        deleted_count = delete_orphan_agents_by_ids([agent.pk])

        assert deleted_count == 0
        assert Agent.objects.filter(pk=agent.pk).exists()

    def test_mixed_agents(self, db):
        """Only orphan agents are deleted from a mixed list."""
        orphan = Agent.objects.create(name="Orphan")
        active = Agent.objects.create(name="Active")
        media = Media.objects.create(title="Test Media", media_type="BOOK")
        media.contributors.add(active)

        deleted_count = delete_orphan_agents_by_ids([orphan.pk, active.pk])

        assert deleted_count == 1
        assert not Agent.objects.filter(pk=orphan.pk).exists()
        assert Agent.objects.filter(pk=active.pk).exists()

    def test_empty_list(self, db):
        """Returns 0 when given an empty list."""
        deleted_count = delete_orphan_agents_by_ids([])

        assert deleted_count == 0

    def test_nonexistent_ids(self, db):
        """Handles non-existent IDs gracefully."""
        deleted_count = delete_orphan_agents_by_ids([99999, 88888])

        assert deleted_count == 0

    def test_handles_none_values(self, db):
        """None values in the list are filtered out."""
        orphan = Agent.objects.create(name="Orphan")

        deleted_count = delete_orphan_agents_by_ids([None, orphan.pk, None])

        assert deleted_count == 1

    def test_handles_duplicate_ids(self, db):
        """Duplicate IDs are handled correctly."""
        orphan = Agent.objects.create(name="Orphan")

        deleted_count = delete_orphan_agents_by_ids([orphan.pk, orphan.pk, orphan.pk])

        assert deleted_count == 1
