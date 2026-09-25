"""
Tests for core.context_processors module.

These tests verify the behavior of context processors.
"""

from django.contrib.auth.models import AnonymousUser
from django.urls import reverse

from core.context_processors import saved_views


def test_user_gets_only_their_own_saved_views(rf, user, other_user, saved_view_factory):
    """A user gets their own saved views, and not those of other users."""
    saved_view_factory(name="View 1")
    saved_view_factory(name="View 2")
    saved_view_factory(user=other_user, name="Other View")
    request = rf.get("/")
    request.user = user

    assert sorted(view.name for view in saved_views(request)["saved_views"]) == ["View 1", "View 2"]


def test_anonymous_user_gets_no_saved_view(rf, db):
    """Anonymous users receive an empty queryset."""
    request = rf.get("/")
    request.user = AnonymousUser()

    assert not saved_views(request)["saved_views"].exists()


def test_saved_views_available_on_all_pages(logged_in_client, saved_view_factory):
    """Saved views are available in context on various pages."""
    saved_view_factory(name="Test View")

    for url_name in ["home", "media_import", "backup_manage"]:
        response = logged_in_client.get(reverse(url_name))
        assert response.context["saved_views"].count() == 1
