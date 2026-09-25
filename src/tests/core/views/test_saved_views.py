"""
Tests for core.views.saved_views: the views saving the filters of the media list.
"""

import pytest
from django.template.loader import render_to_string
from django.urls import reverse

from core.models import SavedView, Tag
from tests.helpers import messages_of


def test_saved_view_save_stores_every_filter_and_applies_them(logged_in_client, user, agent):
    """Saving a view stores every filter of the list, then shows the list with them."""
    tag = Tag.objects.create(name="Favourites")
    data = {
        "view_name": "Complex View",
        "type": ["BOOK", "FILM"],
        "status": ["COMPLETED", "IN_PROGRESS"],
        "score": ["8", "9", "none"],
        "contributor": str(agent.pk),
        "tag": str(tag.pk),
        "review_from": "2024-01",
        "review_to": "2024-12-31",
        "has_review": "filled",
        "has_cover": "empty",
        "sort": "score",
    }

    response = logged_in_client.post(reverse("saved_view_save"), data)

    saved_view = SavedView.objects.get(user=user, name="Complex View")
    assert saved_view.filter_types == ["BOOK", "FILM"]
    assert saved_view.filter_statuses == ["COMPLETED", "IN_PROGRESS"]
    assert saved_view.filter_scores == ["8", "9", "none"]
    assert saved_view.filter_contributor_id == agent.pk
    assert saved_view.filter_tag_id == tag.pk
    assert saved_view.filter_review_from == "2024-01"
    assert saved_view.filter_review_to == "2024-12-31"
    assert saved_view.filter_has_review == "filled"
    assert saved_view.filter_has_cover == "empty"
    assert saved_view.sort == "score"
    assert response.url == saved_view.get_filter_url()


def test_saved_view_save_updates_existing_view(logged_in_client, user, saved_view_factory):
    """POST with existing view name updates the view instead of creating duplicate."""
    saved_view_factory(name="My View", filter_types=["BOOK"], sort="-review_date")

    logged_in_client.post(reverse("saved_view_save"), {"view_name": "My View", "type": ["FILM"], "sort": "-score"})

    saved_view = SavedView.objects.get(user=user)
    assert (saved_view.name, saved_view.filter_types, saved_view.sort) == ("My View", ["FILM"], "-score")


@pytest.mark.parametrize(
    "params",
    [
        {"view_name": ""},
        {"type": "INVALID_TYPE"},
        {"status": "INVALID_STATUS"},
        {"score": "invalid"},
        {"sort": "invalid_field"},
        {"sort": "-updated_at"},
        {"contributor": "99999"},
        {"contributor": "not-a-number"},
        {"tag": "99999"},
        {"review_from": "not-a-date"},
        {"has_review": "invalid"},
        {"has_cover": "invalid"},
    ],
)
def test_saved_view_save_rejects_invalid_filters(logged_in_client, user, params):
    """A view without a name, or with a filter that is not valid, is not saved, and the error is shown."""
    response = logged_in_client.post(reverse("saved_view_save"), {"view_name": "Invalid", **params})

    assert response.url == reverse("home")
    assert not SavedView.objects.filter(user=user).exists()
    assert messages_of(response)


def test_saved_view_actions_ignore_get_requests(logged_in_client, saved_view_factory):
    """GET requests to save or delete a view change nothing and lead back to the list."""
    saved_view = saved_view_factory(name="To Keep")

    for url in [reverse("saved_view_save"), reverse("saved_view_delete", kwargs={"pk": saved_view.pk})]:
        assert logged_in_client.get(url).url == reverse("home")
    assert list(SavedView.objects.values_list("name", flat=True)) == ["To Keep"]


def test_saved_view_delete_removes_view(logged_in_client, saved_view_factory):
    """POST request deletes the saved view."""
    saved_view = saved_view_factory(name="To Delete")

    response = logged_in_client.post(reverse("saved_view_delete", kwargs={"pk": saved_view.pk}))

    assert response.url == reverse("home")
    assert not SavedView.objects.filter(pk=saved_view.pk).exists()


def test_saved_view_delete_only_deletes_own_views(logged_in_client, other_user, saved_view_factory):
    """User cannot delete another user's saved views."""
    other_view = saved_view_factory(user=other_user, name="Other View")

    logged_in_client.post(reverse("saved_view_delete", kwargs={"pk": other_view.pk}))

    assert SavedView.objects.filter(pk=other_view.pk).exists()


def test_saved_view_delete_nonexistent_view(logged_in_client):
    """Deleting a non-existent view redirects with error message."""
    response = logged_in_client.post(reverse("saved_view_delete", kwargs={"pk": 99999}))

    assert response.url == reverse("home")
    assert messages_of(response) == ["View not found"]


def test_saved_view_delete_asks_for_confirmation(logged_in_client, saved_view_factory):
    """Deleting a saved view from the sidebar asks for a confirmation first."""
    saved_view_factory(name="Old view")

    response = logged_in_client.get(reverse("home"))

    assert 'hx-confirm="Delete the view “Old view”?"' in response.content.decode()


def test_save_view_modal_keeps_current_query_parameters(rf, user):
    """The save view form carries every non-empty query parameter, except the page."""
    request = rf.get("/", {"tag": "3", "search": "dune", "type": ["BOOK", "FILM"], "contributor": "", "page": "2"})
    request.user = user

    html = render_to_string("partials/saved_views/save_view_modal.html", request=request)

    for name, value in [("tag", "3"), ("search", "dune"), ("type", "BOOK"), ("type", "FILM")]:
        assert f'name="{name}" value="{value}"' in html
    assert 'name="page"' not in html
    assert 'name="contributor"' not in html
