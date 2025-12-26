"""
Tests for core.forms module.

These tests verify the behavior of the MediaForm.
"""

from core.forms import MediaForm
from core.models import Agent, Media


class TestMediaForm:
    """Tests for the MediaForm."""

    def test_form_valid_with_required_fields(self, db):
        """Form is valid with only required fields."""
        data = {
            "title": "Test Book",
            "media_type": "BOOK",
            "status": "PLANNED",
        }
        form = MediaForm(data=data)

        assert form.is_valid(), form.errors

    def test_form_invalid_without_title(self, db):
        """Form is invalid without a title."""
        data = {
            "media_type": "BOOK",
            "status": "PLANNED",
        }
        form = MediaForm(data=data)

        assert not form.is_valid()
        assert "title" in form.errors

    def test_form_invalid_without_media_type(self, db):
        """Form is invalid without a media type."""
        data = {
            "title": "Test",
            "status": "PLANNED",
        }
        form = MediaForm(data=data)

        assert not form.is_valid()
        assert "media_type" in form.errors

    def test_form_accepts_valid_pub_year(self, db):
        """Form accepts a valid publication year."""
        data = {
            "title": "Test",
            "media_type": "BOOK",
            "status": "PLANNED",
            "pub_year": 2024,
        }
        form = MediaForm(data=data)

        assert form.is_valid(), form.errors

    def test_form_rejects_invalid_pub_year(self, db):
        """Form rejects a publication year outside valid range."""
        data = {
            "title": "Test",
            "media_type": "BOOK",
            "status": "PLANNED",
            "pub_year": -5000,
        }
        form = MediaForm(data=data)

        assert not form.is_valid()
        assert "pub_year" in form.errors

    def test_form_saves_with_contributors(self, db):
        """Form can save a media with existing contributors."""
        agent = Agent.objects.create(name="Author")
        data = {
            "title": "Test",
            "media_type": "BOOK",
            "status": "PLANNED",
            "contributors": [agent.pk],
        }
        form = MediaForm(data=data)

        assert form.is_valid(), form.errors
        media = form.save()
        assert agent in media.contributors.all()

    def test_form_updates_existing_media(self, db):
        """Form can update an existing media instance."""
        media = Media.objects.create(
            title="Original",
            media_type="BOOK",
            status="PLANNED",
        )
        data = {
            "title": "Updated",
            "media_type": "FILM",
            "status": "COMPLETED",
        }
        form = MediaForm(data=data, instance=media)

        assert form.is_valid(), form.errors
        updated = form.save()
        assert updated.pk == media.pk
        assert updated.title == "Updated"
        assert updated.media_type == "FILM"

    def test_form_accepts_all_media_types(self, db):
        """Form accepts all valid media types."""
        valid_types = ["BOOK", "GAME", "MUSIC", "COMIC", "FILM", "TV", "PERF", "BROADCAST"]

        for media_type in valid_types:
            data = {
                "title": f"Test {media_type}",
                "media_type": media_type,
                "status": "PLANNED",
            }
            form = MediaForm(data=data)
            assert form.is_valid(), f"Failed for {media_type}: {form.errors}"

    def test_form_accepts_all_statuses(self, db):
        """Form accepts all valid statuses."""
        valid_statuses = ["PLANNED", "IN_PROGRESS", "COMPLETED", "PAUSED", "DNF"]

        for status in valid_statuses:
            data = {
                "title": f"Test {status}",
                "media_type": "BOOK",
                "status": status,
            }
            form = MediaForm(data=data)
            assert form.is_valid(), f"Failed for {status}: {form.errors}"

    def test_form_accepts_all_scores(self, db):
        """Form accepts all valid scores."""
        for score in range(1, 11):
            data = {
                "title": f"Test score {score}",
                "media_type": "BOOK",
                "status": "COMPLETED",
                "score": score,
            }
            form = MediaForm(data=data)
            assert form.is_valid(), f"Failed for score {score}: {form.errors}"
