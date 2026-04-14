"""
Tests for core.context_processors module.

These tests verify the behavior of context processors.
"""

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import reverse

from core.context_processors import saved_views
from core.models import SavedView


def test_authenticated_user_gets_their_saved_views(user, db):
    """Authenticated users receive their saved views in context."""
    SavedView.objects.create(user=user, name="View 1")
    SavedView.objects.create(user=user, name="View 2")

    factory = RequestFactory()
    request = factory.get("/")
    request.user = user

    result = saved_views(request)

    assert "saved_views" in result
    assert result["saved_views"].count() == 2


def test_authenticated_user_only_gets_own_views(user, django_user_model, db):
    """Users only receive their own saved views, not others'."""
    other_user = django_user_model.objects.create_user(
        username="otheruser",
        email="other@example.com",
        password="testpass123",
    )
    SavedView.objects.create(user=other_user, name="Other View")
    SavedView.objects.create(user=user, name="My View")

    factory = RequestFactory()
    request = factory.get("/")
    request.user = user

    result = saved_views(request)

    assert result["saved_views"].count() == 1
    assert result["saved_views"].first().name == "My View"


def test_anonymous_user_gets_empty_queryset(db):
    """Anonymous users receive an empty queryset."""
    factory = RequestFactory()
    request = factory.get("/")
    request.user = AnonymousUser()

    result = saved_views(request)

    assert "saved_views" in result
    assert result["saved_views"].count() == 0


def test_saved_views_available_on_all_pages(logged_in_client, user, db):
    """Saved views are available in context on various pages."""
    SavedView.objects.create(user=user, name="Test View")

    # Test home page
    response = logged_in_client.get(reverse("home"))
    assert "saved_views" in response.context
    assert response.context["saved_views"].count() == 1

    # Test import page
    response = logged_in_client.get(reverse("media_import"))
    assert "saved_views" in response.context
    assert response.context["saved_views"].count() == 1

    # Test backup manage page
    response = logged_in_client.get(reverse("backup_manage"))
    assert "saved_views" in response.context
    assert response.context["saved_views"].count() == 1
