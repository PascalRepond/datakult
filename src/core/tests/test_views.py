"""
Tests for core.views module.

These tests verify the behavior of views using pytest-django.
"""

import pytest
from django.urls import reverse


class TestIndexView:
    """Tests for the index (home) view."""

    def test_index_requires_login(self, client):
        """The index view requires authentication."""
        url = reverse("home")
        response = client.get(url)

        # Should redirect to login page
        assert response.status_code == 302
        assert "/login/" in response.url

    @pytest.mark.django_db
    def test_index_accessible_when_logged_in(self, client, django_user_model):
        """The index view is accessible when logged in."""
        user = django_user_model.objects.create_user(
            username="testuser",
            password="testpass123",
        )
        client.force_login(user)

        url = reverse("home")
        response = client.get(url)

        assert response.status_code == 200

    @pytest.mark.django_db
    def test_index_displays_media_list(self, client, django_user_model, media):
        """The index view displays the media list."""
        user = django_user_model.objects.create_user(
            username="testuser",
            password="testpass123",
        )
        client.force_login(user)

        url = reverse("home")
        response = client.get(url)

        assert response.status_code == 200
        assert "media_list" in response.context


class TestMediaEditView:
    """Tests for the media_edit view."""

    @pytest.mark.django_db
    def test_media_add_requires_login(self, client):
        """The add media view requires authentication."""
        url = reverse("media_add")
        response = client.get(url)

        assert response.status_code == 302

    @pytest.mark.django_db
    def test_media_edit_requires_login(self, client, media):
        """The edit media view requires authentication."""
        url = reverse("media_edit", kwargs={"pk": media.pk})
        response = client.get(url)

        assert response.status_code == 302


class TestSearchView:
    """Tests for the search view."""

    @pytest.mark.django_db
    def test_search_with_query(self, client, django_user_model, media):
        """Search returns results matching the query."""
        user = django_user_model.objects.create_user(
            username="testuser",
            password="testpass123",
        )
        client.force_login(user)

        url = reverse("search")
        response = client.get(url, {"q": media.title})

        assert response.status_code == 200
