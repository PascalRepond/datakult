"""
Tests for core.views module.

These tests verify the behavior of views using pytest-django.
"""

import re
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import escape
from freezegun import freeze_time

from core.models import Agent, Media, SavedView, Tag
from core.utils import create_backup
from core.views import STATS_COVERS_PER_PAGE


def test_index_accessible_when_logged_in(logged_in_client):
    """The index view is accessible when logged in."""
    response = logged_in_client.get(reverse("home"))

    assert response.status_code == 200


def test_index_displays_media_list(logged_in_client, media):
    """The index view displays the media list."""
    response = logged_in_client.get(reverse("home"))

    assert response.status_code == 200
    assert "media_list" in response.context


def test_index_includes_saved_views_in_context(logged_in_client, user, db):
    """The index view includes saved_views in the context for authenticated users."""
    SavedView.objects.create(user=user, name="View 1")
    SavedView.objects.create(user=user, name="View 2")

    response = logged_in_client.get(reverse("home"))

    assert response.status_code == 200
    assert "saved_views" in response.context
    assert len(response.context["saved_views"]) == 2


def test_media_add_get_displays_form(logged_in_client):
    """GET request displays the form."""
    response = logged_in_client.get(reverse("media_add"))

    assert response.status_code == 200
    assert "form" in response.context


def test_media_add_post_creates_media(logged_in_client, db):
    """POST with valid data creates a new media."""
    data = {
        "title": "New Test Media",
        "media_type": "BOOK",
        "status": "PLANNED",
    }
    response = logged_in_client.post(reverse("media_add"), data)

    assert response.status_code == 302  # Redirect after success
    assert Media.objects.filter(title="New Test Media").exists()


def test_media_add_shows_success_message(logged_in_client, db):
    """Creating a new media shows a success message."""
    data = {
        "title": "New Test Media",
        "media_type": "BOOK",
        "status": "PLANNED",
    }
    response = logged_in_client.post(reverse("media_add"), data, follow=True)

    messages = list(get_messages(response.wsgi_request))
    assert messages
    assert "New Test Media" in str(messages[0])
    assert "created" in str(messages[0]).lower()


def test_media_add_with_new_contributor(logged_in_client, db):
    """POST with new_contributors creates agents and links them."""
    data = {
        "title": "Book with Author",
        "media_type": "BOOK",
        "status": "PLANNED",
        "new_contributors": ["New Author"],
    }
    response = logged_in_client.post(reverse("media_add"), data)

    assert response.status_code == 302
    media = Media.objects.get(title="Book with Author")
    assert media.contributors.filter(name="New Author").exists()


def test_media_edit_get_displays_existing(logged_in_client, media):
    """GET on edit view shows the existing media."""
    response = logged_in_client.get(reverse("media_edit", kwargs={"pk": media.pk}))

    assert response.status_code == 200
    assert response.context["media"] == media


def test_media_edit_post_updates_media(logged_in_client, media):
    """POST updates the existing media."""
    data = {
        "title": "Updated Title",
        "media_type": media.media_type,
        "status": "COMPLETED",
    }
    response = logged_in_client.post(
        reverse("media_edit", kwargs={"pk": media.pk}),
        data,
    )

    assert response.status_code == 302
    media.refresh_from_db()
    assert media.title == "Updated Title"
    assert media.status == "COMPLETED"


def test_media_edit_shows_success_message(logged_in_client, media):
    """Updating a media shows a success message."""
    data = {
        "title": "Updated Title",
        "media_type": media.media_type,
        "status": "COMPLETED",
    }
    response = logged_in_client.post(
        reverse("media_edit", kwargs={"pk": media.pk}),
        data,
        follow=True,
    )

    messages = list(get_messages(response.wsgi_request))
    assert messages
    assert "Updated Title" in str(messages[0])
    assert "updated" in str(messages[0]).lower()


def test_media_edit_removes_contributor_cleans_orphan(logged_in_client, db):
    """Removing a contributor from media deletes orphan agent."""
    agent = Agent.objects.create(name="Soon Orphan")
    media = Media.objects.create(title="Test", media_type="BOOK")
    media.contributors.add(agent)

    data = {
        "title": media.title,
        "media_type": media.media_type,
        "status": media.status,
        "contributors": [],  # Remove the contributor
    }
    logged_in_client.post(reverse("media_edit", kwargs={"pk": media.pk}), data)

    assert not Agent.objects.filter(pk=agent.pk).exists()


def test_media_delete_post_deletes_media(logged_in_client, media):
    """POST request deletes the media."""
    media_pk = media.pk
    response = logged_in_client.post(reverse("media_delete", kwargs={"pk": media_pk}))

    assert response.status_code == 302
    assert not Media.objects.filter(pk=media_pk).exists()


def test_media_delete_shows_success_message(logged_in_client, media):
    """Deleting a media shows a success message with the title."""
    media_title = media.title
    response = logged_in_client.post(
        reverse("media_delete", kwargs={"pk": media.pk}),
        follow=True,
    )

    messages = list(get_messages(response.wsgi_request))
    assert messages
    assert media_title in str(messages[0])
    assert "deleted" in str(messages[0]).lower()


def test_media_delete_cleans_orphan_contributors(logged_in_client, db):
    """Deleting media removes orphan contributors."""
    agent = Agent.objects.create(name="Will Be Orphan")
    media = Media.objects.create(title="To Delete", media_type="BOOK")
    media.contributors.add(agent)

    logged_in_client.post(reverse("media_delete", kwargs={"pk": media.pk}))

    assert not Agent.objects.filter(pk=agent.pk).exists()


def test_media_delete_keeps_shared_contributors(logged_in_client, db):
    """Contributors linked to other media are kept."""
    agent = Agent.objects.create(name="Shared Author")
    media1 = Media.objects.create(title="To Delete", media_type="BOOK")
    media2 = Media.objects.create(title="To Keep", media_type="BOOK")
    media1.contributors.add(agent)
    media2.contributors.add(agent)

    logged_in_client.post(reverse("media_delete", kwargs={"pk": media1.pk}))

    assert Agent.objects.filter(pk=agent.pk).exists()


def test_media_delete_get_redirects(logged_in_client, media):
    """GET request redirects to edit page (no delete)."""
    response = logged_in_client.get(reverse("media_delete", kwargs={"pk": media.pk}))

    assert response.status_code == 302
    assert f"/media/{media.pk}/edit/" in response.url
    assert Media.objects.filter(pk=media.pk).exists()


def test_search_with_query(logged_in_client, media):
    """Search returns results matching the query."""
    response = logged_in_client.get(reverse("home"), {"search": media.title})

    assert response.status_code == 200


def test_search_by_title(logged_in_client, media_factory):
    """Search finds media by title."""
    media_factory(title="Unique Title Here")
    media_factory(title="Other Book")

    response = logged_in_client.get(reverse("home"), {"search": "Unique"})

    assert len(response.context["media_list"]) == 1


def test_search_by_contributor(logged_in_client, db):
    """Search finds media by contributor name."""
    agent = Agent.objects.create(name="Famous Author")
    media = Media.objects.create(title="Some Book", media_type="BOOK")
    media.contributors.add(agent)

    response = logged_in_client.get(reverse("home"), {"search": "Famous"})

    assert media in response.context["media_list"]


def test_agent_search_returns_matching_agents(logged_in_client, db):
    """Search returns agents matching the query."""
    Agent.objects.create(name="John Doe")
    Agent.objects.create(name="Jane Doe")
    Agent.objects.create(name="Bob Smith")

    response = logged_in_client.get(reverse("agent_search_htmx"), {"q": "Doe"})

    assert response.status_code == 200
    assert len(response.context["agents"]) == 2


def test_agent_search_empty_query(logged_in_client, agent):
    """Empty query returns no agents."""
    response = logged_in_client.get(reverse("agent_search_htmx"), {"q": ""})

    assert response.status_code == 200
    assert len(response.context["agents"]) == 0


def test_agent_search_limits_results(logged_in_client, db):
    """Search limits results to 12."""
    for i in range(20):
        Agent.objects.create(name=f"Agent {i}")

    response = logged_in_client.get(reverse("agent_search_htmx"), {"q": "Agent"})

    assert len(response.context["agents"]) == 12


def test_agent_select_returns_chip(logged_in_client, agent):
    """Selecting an agent returns the chip template."""
    response = logged_in_client.post(
        reverse("agent_select_htmx"),
        {"id": agent.pk},
    )

    assert response.status_code == 200
    assert response.context["agent"] == agent


def test_agent_select_nonexistent(logged_in_client, db):
    """Selecting a non-existent agent returns error."""
    response = logged_in_client.post(
        reverse("agent_select_htmx"),
        {"id": 99999},
    )

    assert response.status_code == 200
    assert response.context["error"] == "Agent not found"


def test_default_sorting(logged_in_client):
    """Default sorting is by review_date descending."""
    response = logged_in_client.get(reverse("home"))

    assert response.context["sort"] == "-review_date"


def test_custom_sorting(logged_in_client):
    """Custom sorting is applied."""
    response = logged_in_client.get(reverse("home"), {"sort": "score"})

    assert response.context["sort"] == "score"


@pytest.mark.parametrize("sort", ["invalid_field", "-updated_at", "created_at"])
def test_sort_outside_the_options_uses_default(logged_in_client, sort):
    """A sort that is not one of the sort options, such as a removed one, falls back to the default sort."""
    response = logged_in_client.get(reverse("home"), {"sort": sort})

    assert response.context["sort"] == "-review_date"


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        ("-score", ["Great", "Poor", "Undated and unrated"]),
        ("score", ["Poor", "Great", "Undated and unrated"]),
        ("-review_date", ["Great", "Poor", "Undated and unrated"]),
        ("review_date", ["Poor", "Great", "Undated and unrated"]),
    ],
)
def test_media_without_the_sorted_value_come_last(logged_in_client, media_factory, sort, expected):
    """Unrated or undated media come after the others, whatever the direction of the sort."""
    media_factory(title="Undated and unrated")
    media_factory(title="Poor", score=3, review_date="2020")
    media_factory(title="Great", score=9, review_date="2024-05")

    response = logged_in_client.get(reverse("home"), {"sort": sort})

    assert [media.title for media in response.context["media_list"]] == expected


def test_media_without_sorted_value_are_sorted_by_last_update(logged_in_client, media_factory):
    """Media that tie on the sort, such as unreviewed ones, come last updated first."""
    with freeze_time("2026-01-01"):
        older = media_factory(title="Older")
    with freeze_time("2026-02-01"):
        newer = media_factory(title="Newer")

    response = logged_in_client.get(reverse("home"))

    assert list(response.context["media_list"]) == [newer, older]
    with freeze_time("2026-03-01"):
        older.save()
    assert list(logged_in_client.get(reverse("home")).context["media_list"]) == [older, newer]


def test_filter_by_type(logged_in_client, media_factory):
    """Filtering by media type works."""
    media_factory(title="A Book", media_type="BOOK")
    media_factory(title="A Film", media_type="FILM")

    response = logged_in_client.get(reverse("home"), {"type": "BOOK"})

    titles = [m.title for m in response.context["media_list"]]
    assert "A Book" in titles
    assert "A Film" not in titles


def test_filter_by_status(logged_in_client, media_factory):
    """Filtering by status works."""
    media_factory(title="Planned", status="PLANNED")
    media_factory(title="Completed", status="COMPLETED")

    response = logged_in_client.get(reverse("home"), {"status": "COMPLETED"})

    titles = [m.title for m in response.context["media_list"]]
    assert "Completed" in titles
    assert "Planned" not in titles


def test_filter_by_contributor(logged_in_client, db):
    """Filtering by contributor works."""
    agent = Agent.objects.create(name="Specific Author")
    media = Media.objects.create(title="By Author", media_type="BOOK")
    media.contributors.add(agent)
    Media.objects.create(title="No Author", media_type="BOOK")

    response = logged_in_client.get(reverse("home"), {"contributor": agent.pk})

    titles = [m.title for m in response.context["media_list"]]
    assert "By Author" in titles
    assert "No Author" not in titles


def test_filter_by_no_score(logged_in_client, media_factory):
    """Filtering by 'no score' works."""
    media_factory(title="Rated", score=8)
    media_factory(title="Unrated", score=None)

    response = logged_in_client.get(reverse("home"), {"score": "none"})

    titles = [m.title for m in response.context["media_list"]]
    assert "Unrated" in titles
    assert "Rated" not in titles


def test_filter_with_invalid_date_ignores_filter(logged_in_client, media_factory):
    """Invalid date values in URL are silently ignored."""
    media_factory(title="Recent", review_date="2025-01-01")
    media_factory(title="Old", review_date="2020-01-01")

    # Try with invalid date format - should not crash and return all results
    response = logged_in_client.get(reverse("home"), {"review_from": "not-a-date"})

    assert response.status_code == 200
    titles = [m.title for m in response.context["media_list"]]
    # Both should be present since the invalid filter was ignored
    assert "Recent" in titles
    assert "Old" in titles


def test_filter_review_from_includes_less_precise_dates(logged_in_client, media_factory):
    """A start date includes review dates with a year or month precision that begin on that day."""
    media_factory(title="Year", review_date="2016")
    media_factory(title="January", review_date="2016-01")
    media_factory(title="March", review_date="2016-03")
    media_factory(title="March 2nd", review_date="2016-03-02")
    media_factory(title="Before", review_date="2015-12-31")

    from_new_year = logged_in_client.get(reverse("home"), {"review_from": "2016-01-01"})
    from_march = logged_in_client.get(reverse("home"), {"review_from": "2016-03-01"})
    from_march_2nd = logged_in_client.get(reverse("home"), {"review_from": "2016-03-02"})

    assert {m.title for m in from_new_year.context["media_list"]} == {"Year", "January", "March", "March 2nd"}
    assert {m.title for m in from_march.context["media_list"]} == {"March", "March 2nd"}
    assert {m.title for m in from_march_2nd.context["media_list"]} == {"March 2nd"}


def test_media_review_modal_shows_the_full_review(logged_in_client, media_factory):
    """The review modal shows the whole rendered review, with links to edit the media and to its page."""
    media = media_factory(review="**Bold text** " + "word " * 80, score=8)

    response = logged_in_client.get(reverse("media_review_htmx", kwargs={"pk": media.pk}))
    content = response.content.decode()

    assert "<strong>Bold text</strong>" in content
    assert content.count("word") == 80
    assert f'href="{reverse("media_edit", args=[media.pk])}"' in content
    assert f'href="{reverse("media_detail", args=[media.pk])}"' in content


def test_media_review_modal_of_missing_media_returns_404(logged_in_client, db):
    """The review modal of a media that does not exist is not found."""
    response = logged_in_client.get(reverse("media_review_htmx", kwargs={"pk": 99999}))

    assert response.status_code == 404


def test_media_card_offers_to_read_more_of_a_long_review(logged_in_client, media_factory):
    """A card shows a plain text excerpt of the review, cut when long and then opening the whole review in the modal."""
    long_review = media_factory(review="**Bold text** " + "word " * 40)
    short_review = media_factory(review="Short and cosy.")

    content = logged_in_client.get(reverse("home")).content.decode()

    assert f'hx-get="{reverse("media_review_htmx", args=[long_review.pk])}"' in content
    assert f'hx-get="{reverse("media_review_htmx", args=[short_review.pk])}"' not in content
    assert "Bold text word" in content
    assert "word " * 20 not in content
    assert "<strong>Bold text</strong>" not in content
    assert "Short and cosy." in content


def test_empty_library_invites_to_add_a_first_media(logged_in_client, db):
    """With no media at all, the list invites to add one."""
    content = logged_in_client.get(reverse("home")).content.decode()

    assert "Add your first media" in content
    assert "Clear filters</a>" not in content


def test_empty_results_offer_to_clear_the_filters(logged_in_client, media_factory):
    """When filters or a search match nothing, the list offers to clear them."""
    media_factory(title="Dune")

    content = logged_in_client.get(reverse("home"), {"search": "nothing matches"}).content.decode()

    assert "Add your first media" not in content
    assert re.search(r'href="/"[^>]*>\s*(<svg[\s\S]*?</svg>)?\s*Clear filters', content)


def test_backup_manage_displays_page(logged_in_client):
    """The backup manage view displays the backup management page."""
    response = logged_in_client.get(reverse("backup_manage"))

    assert response.status_code == 200
    assert "base/backup_manage.html" in [t.name for t in response.templates]


def test_backup_export_creates_and_downloads_backup(logged_in_client, db, monkeypatch, tmp_path):
    """The backup export view creates and returns a backup file."""
    # Write the backup to a temporary directory instead of the project's backups folder
    monkeypatch.setattr("core.views.create_backup", lambda: create_backup(output_dir=tmp_path))
    # Create some test data
    Media.objects.create(title="Test Media", media_type="BOOK")

    response = logged_in_client.get(reverse("backup_export"))

    # Should return a file download
    assert response.status_code == 200
    assert len(list(tmp_path.glob("datakult_backup_*.tar.gz"))) == 1
    # Django's FileResponse detects .tar.gz as gzip
    assert response["Content-Type"] == "application/gzip"
    assert "attachment" in response["Content-Disposition"]
    assert "datakult_backup_" in response["Content-Disposition"]


def test_backup_export_handles_errors_gracefully(logged_in_client, monkeypatch):
    """The backup export view handles errors and redirects with message."""

    def mock_create_backup(*args, **kwargs):
        msg = "Test error"
        raise OSError(msg)

    monkeypatch.setattr("core.views.create_backup", mock_create_backup)

    response = logged_in_client.get(reverse("backup_export"))

    # Should redirect back to backup manage with error message
    assert response.status_code == 302
    assert response.url == reverse("backup_manage")


def test_backup_import_get_redirects(logged_in_client):
    """GET requests to backup import redirect to backup manage."""
    response = logged_in_client.get(reverse("backup_import"))

    assert response.status_code == 302
    assert response.url == reverse("backup_manage")


def test_backup_import_requires_file(logged_in_client):
    """The backup import view requires a file to be uploaded."""
    response = logged_in_client.post(reverse("backup_import"))

    assert response.status_code == 302
    # Should redirect back with error message


def test_backup_import_rejects_invalid_format(logged_in_client):
    """The backup import view rejects files with invalid format."""
    invalid_file = SimpleUploadedFile("backup.txt", b"not a backup", content_type="text/plain")

    response = logged_in_client.post(reverse("backup_import"), {"backup_file": invalid_file})

    assert response.status_code == 302
    assert response.url == reverse("backup_manage")


def test_backup_import_restores_data(logged_in_client, db):
    """The backup import view successfully restores data from a backup."""
    # Create test data and backup
    original_media = Media.objects.create(title="Original Media", media_type="BOOK", status="COMPLETED")

    with TemporaryDirectory() as tmpdir:
        # Create a backup
        backup_path = create_backup(output_dir=Path(tmpdir))

        # Clear the database
        Media.objects.all().delete()
        assert Media.objects.count() == 0

        # Import the backup via the view
        with backup_path.open("rb") as backup_file:
            uploaded_file = SimpleUploadedFile(backup_path.name, backup_file.read(), content_type="application/x-tar")
            response = logged_in_client.post(reverse("backup_import"), {"backup_file": uploaded_file})

        # Should redirect to home
        assert response.status_code == 302
        assert response.url == reverse("home")

        # Data should be restored
        assert Media.objects.count() == 1
        restored_media = Media.objects.first()
        assert restored_media.title == original_media.title
        assert restored_media.status == original_media.status


def test_backup_import_handles_errors(logged_in_client):
    """The backup import view handles errors gracefully."""
    # Create a valid tar.gz file with invalid content
    invalid_file = SimpleUploadedFile("backup.tar.gz", b"invalid content", content_type="application/x-tar")

    response = logged_in_client.post(reverse("backup_import"), {"backup_file": invalid_file})

    # Should redirect back to backup manage with error message
    assert response.status_code == 302
    assert response.url == reverse("backup_manage")


def test_index_paginates_results_across_pages(logged_in_client, media_factory):
    """Index view paginates results with 20 items per page and navigates correctly."""
    # Create 25 media items
    for i in range(25):
        media_factory(title=f"Media {i}")

    # Test first page
    response_page1 = logged_in_client.get(reverse("home"))
    assert response_page1.status_code == 200
    assert "page_obj" in response_page1.context
    assert len(response_page1.context["media_list"]) == 20
    assert response_page1.context["page_obj"].has_next()

    # Test second page
    response_page2 = logged_in_client.get(reverse("home"), {"page": 2})
    assert response_page2.status_code == 200
    assert len(response_page2.context["media_list"]) == 5
    assert response_page2.context["page_obj"].has_previous()
    assert not response_page2.context["page_obj"].has_next()


def test_search_paginates_results(logged_in_client, media_factory):
    """Search view paginates results."""
    # Create 25 media items with searchable title
    for i in range(25):
        media_factory(title=f"Searchable {i}")

    response = logged_in_client.get(reverse("home"), {"search": "Searchable"})

    assert response.status_code == 200
    assert len(response.context["media_list"]) == 20
    assert response.context["page_obj"].has_next()


def test_load_more_returns_partial_template(logged_in_client, media_factory):
    """Load more view returns the media-items-page partial template."""
    for i in range(25):
        media_factory(title=f"Media {i}")

    response = logged_in_client.get(reverse("load_more_media"), {"page": 2})

    assert response.status_code == 200
    assert "partials/media_items/media_list_page.html" in [t.name for t in response.templates]


def test_load_more_returns_next_page_items(logged_in_client, media_factory):
    """Load more view returns items for the requested page."""
    # Create 25 items
    for i in range(25):
        media_factory(title=f"Media {i:02d}")

    # Request page 2 (items 21-25)
    response = logged_in_client.get(reverse("load_more_media"), {"page": 2})

    assert response.status_code == 200
    assert len(response.context["media_list"]) == 5


def test_load_more_preserves_sorting(logged_in_client, media_factory):
    """Load more view preserves sort order from initial request."""
    media_factory(title="A", score=5)
    media_factory(title="B", score=8)
    media_factory(title="C", score=3)

    response = logged_in_client.get(reverse("load_more_media"), {"page": 1, "sort": "score"})

    assert response.status_code == 200
    scores = [m.score for m in response.context["media_list"] if m.score is not None]
    # Should be sorted ascending by score
    assert scores == sorted(scores)


def test_load_more_preserves_filters(logged_in_client, media_factory):
    """Load more view preserves filters from initial request."""
    media_factory(title="Book 1", media_type="BOOK")
    media_factory(title="Film 1", media_type="FILM")
    media_factory(title="Book 2", media_type="BOOK")

    response = logged_in_client.get(reverse("load_more_media"), {"page": 1, "type": "BOOK"})

    assert response.status_code == 200
    media_types = [m.media_type for m in response.context["media_list"]]
    assert all(mt == "BOOK" for mt in media_types)


def test_load_more_with_search_query(logged_in_client, media_factory):
    """Load more view applies search query when provided."""
    media_factory(title="Python Guide")
    media_factory(title="JavaScript Guide")
    media_factory(title="Python Cookbook")

    response = logged_in_client.get(reverse("load_more_media"), {"page": 1, "search": "Python"})

    assert response.status_code == 200
    assert len(response.context["media_list"]) == 2
    titles = [m.title for m in response.context["media_list"]]
    assert all("Python" in title for title in titles)


def test_load_more_page_obj_pagination_state(logged_in_client, media_factory):
    """Load more view sets has_next correctly across different page states."""
    # Create 45 items (3 pages of 20 items each)
    for i in range(45):
        media_factory(title=f"Media {i}")

    # Test page 2 (middle page) - should have next
    response_page2 = logged_in_client.get(reverse("load_more_media"), {"page": 2})
    assert response_page2.status_code == 200
    assert response_page2.context["page_obj"].has_next()
    assert response_page2.context["page_obj"].number == 2

    # Test page 3 (last page) - should not have next
    response_page3 = logged_in_client.get(reverse("load_more_media"), {"page": 3})
    assert response_page3.status_code == 200
    assert not response_page3.context["page_obj"].has_next()
    assert response_page3.context["page_obj"].number == 3


def test_media_detail_accessible_when_logged_in(logged_in_client, media):
    """The detail view is accessible when logged in."""
    response = logged_in_client.get(reverse("media_detail", kwargs={"pk": media.pk}))

    assert response.status_code == 200
    assert response.context["media"] == media


def test_media_detail_displays_correct_template(logged_in_client, media):
    """The detail view uses the media_detail template."""
    response = logged_in_client.get(reverse("media_detail", kwargs={"pk": media.pk}))

    assert response.status_code == 200
    assert "base/media_detail.html" in [t.name for t in response.templates]


def test_media_detail_nonexistent_returns_404(logged_in_client):
    """Accessing detail view with nonexistent media returns 404."""
    response = logged_in_client.get(reverse("media_detail", kwargs={"pk": 99999}))

    assert response.status_code == 404


def test_media_detail_shows_all_fields(logged_in_client, db):
    """The detail view displays all media fields."""
    agent = Agent.objects.create(name="Test Author")
    media = Media.objects.create(
        title="Complete Media",
        media_type="BOOK",
        status="COMPLETED",
        score=8,
        review="This is a detailed review.",
        pub_year=2023,
        external_uri="https://example.com",
    )
    media.contributors.add(agent)

    response = logged_in_client.get(reverse("media_detail", kwargs={"pk": media.pk}))
    content = response.content.decode("utf-8")

    assert media.title in content
    assert "2023" in content
    assert agent.name in content
    assert "https://example.com" in content


def test_media_detail_contributor_links_to_filtered_list(logged_in_client, db):
    """Contributor links in detail view navigate to filtered home page."""
    agent = Agent.objects.create(name="Test Contributor")
    media = Media.objects.create(
        title="Test Media",
        media_type="BOOK",
    )
    media.contributors.add(agent)

    response = logged_in_client.get(reverse("media_detail", kwargs={"pk": media.pk}))
    content = response.content.decode("utf-8")

    # Should contain a link to home with contributor filter
    assert f"contributor={agent.id}" in content
    assert 'class="link link-hover contributor-link"' in content
    # Should NOT contain HTMX attributes for contributor links
    assert "hx-target" not in content


def test_saved_view_save_creates_new_view(logged_in_client, user, db):
    """POST with valid data creates a new saved view."""
    data = {
        "view_name": "My Books",
        "type": ["BOOK"],
        "status": ["COMPLETED"],
        "score": ["8", "9"],
        "sort": "-score",
    }
    response = logged_in_client.post(reverse("saved_view_save"), data)

    # Should redirect to home with filters applied
    assert response.status_code == 302
    assert "/" in response.url

    # View should be created in database
    assert SavedView.objects.filter(user=user, name="My Books").exists()
    saved_view = SavedView.objects.get(user=user, name="My Books")
    assert saved_view.filter_types == ["BOOK"]
    assert saved_view.filter_statuses == ["COMPLETED"]
    assert saved_view.filter_scores == ["8", "9"]
    assert saved_view.sort == "-score"


def test_saved_view_save_updates_existing_view(logged_in_client, user, db):
    """POST with existing view name updates the view instead of creating duplicate."""
    # Create initial view
    SavedView.objects.create(
        user=user,
        name="My View",
        filter_types=["BOOK"],
        sort="-review_date",
    )

    # Update with different filters
    data = {
        "view_name": "My View",
        "type": ["FILM"],
        "sort": "-score",
    }
    response = logged_in_client.post(reverse("saved_view_save"), data)

    assert response.status_code == 302

    # Should still be only one view with that name
    assert SavedView.objects.filter(user=user, name="My View").count() == 1

    # View should be updated
    saved_view = SavedView.objects.get(user=user, name="My View")
    assert saved_view.filter_types == ["FILM"]
    assert saved_view.sort == "-score"


def test_saved_view_save_requires_view_name(logged_in_client, user, db):
    """POST without view_name redirects with error message."""
    data = {
        "type": ["BOOK"],
    }
    response = logged_in_client.post(reverse("saved_view_save"), data)

    # Should redirect back to home
    assert response.status_code == 302

    # No view should be created
    assert SavedView.objects.filter(user=user).count() == 0


def test_saved_view_save_get_redirects(logged_in_client):
    """GET request redirects to home."""
    response = logged_in_client.get(reverse("saved_view_save"))

    assert response.status_code == 302
    assert response.url == reverse("home")


def test_saved_view_save_stores_all_filter_types(logged_in_client, user, db):
    """All filter parameters are correctly stored."""
    from core.models import Agent

    agent = Agent.objects.create(name="Test Author")

    data = {
        "view_name": "Complex View",
        "type": ["BOOK", "FILM"],
        "status": ["COMPLETED", "IN_PROGRESS"],
        "score": ["8", "9", "10"],
        "contributor": str(agent.pk),
        "review_from": "2024-01-01",
        "review_to": "2024-12-31",
        "has_review": "filled",
        "has_cover": "empty",
        "sort": "score",
    }
    response = logged_in_client.post(reverse("saved_view_save"), data)

    assert response.status_code == 302

    saved_view = SavedView.objects.get(user=user, name="Complex View")
    assert saved_view.filter_types == ["BOOK", "FILM"]
    assert saved_view.filter_statuses == ["COMPLETED", "IN_PROGRESS"]
    assert saved_view.filter_scores == ["8", "9", "10"]
    assert saved_view.filter_contributor_id == agent.pk
    assert saved_view.filter_review_from == "2024-01-01"
    assert saved_view.filter_review_to == "2024-12-31"
    assert saved_view.filter_has_review == "filled"
    assert saved_view.filter_has_cover == "empty"
    assert saved_view.sort == "score"


def test_saved_view_save_redirects_with_filters(logged_in_client, user, db):
    """After saving, redirects to home with all filters applied in URL."""
    data = {
        "view_name": "Filtered View",
        "type": ["BOOK"],
        "status": ["COMPLETED"],
        "sort": "-score",
    }
    response = logged_in_client.post(reverse("saved_view_save"), data)

    assert response.status_code == 302
    # URL should contain the filters
    assert "type=BOOK" in response.url
    assert "status=COMPLETED" in response.url
    assert "sort=-score" in response.url


def test_saved_view_delete_removes_view(logged_in_client, user, db):
    """POST request deletes the saved view."""
    saved_view = SavedView.objects.create(user=user, name="To Delete")

    response = logged_in_client.post(reverse("saved_view_delete", kwargs={"pk": saved_view.pk}))

    assert response.status_code == 302
    assert response.url == reverse("home")
    assert not SavedView.objects.filter(pk=saved_view.pk).exists()


def test_saved_view_delete_only_deletes_own_views(logged_in_client, user, django_user_model, db):
    """User cannot delete another user's saved views."""
    other_user = django_user_model.objects.create_user(
        username="otheruser",
        email="other@example.com",
        password="testpass123",
    )
    other_view = SavedView.objects.create(user=other_user, name="Other View")

    response = logged_in_client.post(reverse("saved_view_delete", kwargs={"pk": other_view.pk}))

    # Should redirect but view should still exist
    assert response.status_code == 302
    assert SavedView.objects.filter(pk=other_view.pk).exists()


def test_saved_view_delete_nonexistent_view(logged_in_client, db):
    """Deleting a non-existent view redirects with error message."""
    response = logged_in_client.post(reverse("saved_view_delete", kwargs={"pk": 99999}))

    assert response.status_code == 302
    assert response.url == reverse("home")


def test_saved_view_delete_get_redirects(logged_in_client, user, db):
    """GET request redirects to home without deleting."""
    saved_view = SavedView.objects.create(user=user, name="To Keep")

    response = logged_in_client.get(reverse("saved_view_delete", kwargs={"pk": saved_view.pk}))

    assert response.status_code == 302
    assert response.url == reverse("home")
    assert SavedView.objects.filter(pk=saved_view.pk).exists()


def test_saved_view_rejects_invalid_media_type(logged_in_client, user, db):
    """Saved view validation rejects invalid media types."""
    data = {
        "view_name": "Invalid Type View",
        "type": ["INVALID_TYPE"],
        "sort": "-review_date",
    }
    response = logged_in_client.post(reverse("saved_view_save"), data, follow=True)

    # Should redirect back to home with error
    assert response.status_code == 200
    # View should not be created
    assert not SavedView.objects.filter(user=user, name="Invalid Type View").exists()


def test_saved_view_rejects_invalid_status(logged_in_client, user, db):
    """Saved view validation rejects invalid statuses."""
    data = {
        "view_name": "Invalid Status View",
        "status": ["INVALID_STATUS"],
        "sort": "-review_date",
    }
    logged_in_client.post(reverse("saved_view_save"), data)

    # View should not be created
    assert not SavedView.objects.filter(user=user, name="Invalid Status View").exists()


def test_saved_view_rejects_invalid_score(logged_in_client, user, db):
    """Saved view validation rejects invalid scores."""
    data = {
        "view_name": "Invalid Score View",
        "score": ["invalid"],
        "sort": "-review_date",
    }
    logged_in_client.post(reverse("saved_view_save"), data)

    # View should not be created
    assert not SavedView.objects.filter(user=user, name="Invalid Score View").exists()


@pytest.mark.parametrize("sort", ["invalid_field", "-updated_at"])
def test_saved_view_rejects_invalid_sort_field(logged_in_client, user, db, sort):
    """Saved view validation rejects sorts that are not one of the sort options."""
    data = {
        "view_name": "Invalid Sort View",
        "sort": sort,
    }
    logged_in_client.post(reverse("saved_view_save"), data)

    # View should not be created
    assert not SavedView.objects.filter(user=user, name="Invalid Sort View").exists()


def test_saved_view_rejects_nonexistent_contributor(logged_in_client, user, db):
    """Saved view validation rejects non-existent contributor IDs."""
    data = {
        "view_name": "Invalid Contributor View",
        "contributor": "99999",
        "sort": "-review_date",
    }
    logged_in_client.post(reverse("saved_view_save"), data)

    # View should not be created
    assert not SavedView.objects.filter(user=user, name="Invalid Contributor View").exists()


def test_saved_view_rejects_invalid_contributor_format(logged_in_client, user, db):
    """Saved view validation rejects invalid contributor ID formats."""
    data = {
        "view_name": "Invalid Contributor Format",
        "contributor": "not-a-number",
        "sort": "-review_date",
    }
    logged_in_client.post(reverse("saved_view_save"), data)

    # View should not be created
    assert not SavedView.objects.filter(user=user, name="Invalid Contributor Format").exists()


def test_saved_view_rejects_invalid_date_format(logged_in_client, user, db):
    """Saved view validation rejects invalid date formats."""
    data = {
        "view_name": "Invalid Date View",
        "review_from": "not-a-date",
        "sort": "-review_date",
    }
    logged_in_client.post(reverse("saved_view_save"), data)

    # View should not be created
    assert not SavedView.objects.filter(user=user, name="Invalid Date View").exists()


def test_saved_view_rejects_invalid_has_review_value(logged_in_client, user, db):
    """Saved view validation rejects invalid has_review values."""
    data = {
        "view_name": "Invalid Has Review",
        "has_review": "invalid",
        "sort": "-review_date",
    }
    logged_in_client.post(reverse("saved_view_save"), data)

    # View should not be created
    assert not SavedView.objects.filter(user=user, name="Invalid Has Review").exists()


def test_saved_view_rejects_invalid_has_cover_value(logged_in_client, user, db):
    """Saved view validation rejects invalid has_cover values."""
    data = {
        "view_name": "Invalid Has Cover",
        "has_cover": "invalid",
        "sort": "-review_date",
    }
    logged_in_client.post(reverse("saved_view_save"), data)

    # View should not be created
    assert not SavedView.objects.filter(user=user, name="Invalid Has Cover").exists()


def test_saved_view_accepts_valid_data(logged_in_client, user, db):
    """Saved view validation accepts all valid data."""
    agent = Agent.objects.create(name="Valid Author")

    data = {
        "view_name": "Valid View",
        "type": ["BOOK", "FILM"],
        "status": ["COMPLETED"],
        "score": ["8", "9", "none"],
        "contributor": str(agent.pk),
        "review_from": "2024-01",
        "review_to": "2024-12-31",
        "has_review": "filled",
        "has_cover": "empty",
        "sort": "-score",
    }
    response = logged_in_client.post(reverse("saved_view_save"), data)

    # Should redirect successfully
    assert response.status_code == 302

    # View should be created
    assert SavedView.objects.filter(user=user, name="Valid View").exists()
    saved_view = SavedView.objects.get(user=user, name="Valid View")
    assert saved_view.filter_types == ["BOOK", "FILM"]
    assert saved_view.filter_statuses == ["COMPLETED"]
    assert saved_view.filter_scores == ["8", "9", "none"]
    assert saved_view.filter_contributor_id == agent.pk
    assert saved_view.filter_review_from == "2024-01"
    assert saved_view.filter_review_to == "2024-12-31"
    assert saved_view.filter_has_review == "filled"
    assert saved_view.filter_has_cover == "empty"
    assert saved_view.sort == "-score"


# Statistics view


@pytest.mark.parametrize("url_name", ["stats", "stats_covers_htmx"])
def test_stats_requires_login(client, db, url_name):
    """The stats views redirect anonymous users to the login page."""
    response = client.get(reverse(url_name))

    assert response.status_code == 302


def test_stats_only_counts_rated_media(logged_in_client, media_factory):
    """Only rated media are counted, whatever their status."""
    media_factory(status="COMPLETED", review_date="2024", score=8)
    media_factory(status="DNF", review_date="2024", score=4)
    media_factory(status="COMPLETED", review_date="2023")

    response = logged_in_client.get(reverse("stats"))

    assert response.context["overview"] == {"count": 2, "average_score": 6.0}
    assert response.context["years"] == [2024]
    assert sum(row["count"] for row in response.context["type_counts"]) == 2


def test_stats_all_years_shows_yearly_chart(logged_in_client, media_factory):
    """Without a year, the yearly chart replaces the monthly one."""
    media_factory(review_date="2023-03-15", score=8)
    media_factory(review_date="2024-03-15", score=6)

    response = logged_in_client.get(reverse("stats"))

    assert response.status_code == 200
    assert [row["label"] for row in response.context["per_year"]] == [2023, 2024]
    assert response.context["per_month"] is None


def test_stats_year_shows_monthly_chart(logged_in_client, media_factory):
    """Selecting a year restricts the page to that year and shows the monthly chart instead of the yearly one."""
    media_factory(review_date="2023-06", score=2)
    media_factory(review_date="2024-03-15", score=8)

    response = logged_in_client.get(reverse("stats"), {"year": "2024"})

    assert response.context["year"] == 2024
    assert response.context["overview"] == {"count": 1, "average_score": 8.0}
    assert response.context["per_year"] is None
    assert response.context["per_month"][2]["count"] == 1


def test_stats_year_navigation(logged_in_client, media_factory):
    """The selected year comes with the previous and next years that have rated media."""
    for review_date in ("2018", "2020-05", "2023-01-01"):
        media_factory(review_date=review_date, score=5)

    response = logged_in_client.get(reverse("stats"), {"year": "2020"})

    assert (response.context["previous_year"], response.context["next_year"]) == (2018, 2023)


@pytest.mark.parametrize("params", [{"type": "BOOK"}, {"type": "BOOK", "year": "2024"}])
def test_stats_years_follow_the_media_type(logged_in_client, media_factory, params):
    """The year picker only offers the years with rated media of the selected type, with or without a year."""
    media_factory(media_type="BOOK", review_date="2020", score=5)
    media_factory(media_type="FILM", review_date="2022", score=5)
    media_factory(media_type="BOOK", review_date="2024-06", score=5)

    response = logged_in_client.get(reverse("stats"), params)

    assert response.context["years"] == [2024, 2020]


def test_stats_type_filter(logged_in_client, media_factory):
    """A media type restricts the charts, while the type counters still show every type."""
    media_factory(media_type="BOOK", review_date="2024", score=9)
    media_factory(media_type="FILM", review_date="2024", score=3)

    response = logged_in_client.get(reverse("stats"), {"type": "FILM"})

    assert (response.context["media_type"], response.context["media_type_label"]) == ("FILM", "Film")
    assert response.context["overview"] == {"count": 1, "average_score": 3.0}
    assert response.context["score_distribution"][2]["count"] == 1
    assert response.context["score_distribution"][8]["count"] == 0
    counts = {row["media_type"]: row["count"] for row in response.context["type_counts"]}
    assert (counts["BOOK"], counts["FILM"]) == (1, 1)


@pytest.mark.parametrize("year", ["abc", "0", "9999", pytest.param("1" * 5000, id="oversized")])
def test_stats_invalid_filters_are_ignored(logged_in_client, media_factory, year):
    """Invalid type and year parameters, years out of the review date range included, fall back to everything."""
    media_factory(score=5)

    response = logged_in_client.get(reverse("stats"), {"year": year, "type": "NOPE"})

    assert response.context["year"] is None
    assert response.context["media_type"] is None
    assert response.context["overview"]["count"] == 1


def test_stats_covers_first_page(logged_in_client, media_factory):
    """The first page of covers shows rated media only, best scores first, then latest reviews."""
    media_factory(title="Unrated", review_date="2024-12-31")
    for day in range(1, STATS_COVERS_PER_PAGE + 2):
        media_factory(title=f"Day {day}", review_date=f"2024-01-{day % 28 + 1:02d}", score=5)
    older_best = media_factory(title="Older best", review_date="2023-05", score=9)
    newer_best = media_factory(title="Newer best", review_date="2024-02", score=9)
    top = media_factory(title="Top", review_date="2020", score=10)

    response = logged_in_client.get(reverse("stats"))

    covers = response.context["covers"]
    assert len(covers) == STATS_COVERS_PER_PAGE
    assert list(covers[:3]) == [top, newer_best, older_best]
    assert 'aria-label="Top, Score: 10 out of 10"' in response.content.decode("utf-8")
    assert "Unrated" not in [media.title for media in covers.object_list]
    assert covers.has_next()


def test_stats_covers_htmx_returns_next_page_with_filters(logged_in_client, media_factory):
    """The covers endpoint returns the requested page, keeping the year and type filters."""
    for _ in range(STATS_COVERS_PER_PAGE + 1):
        media_factory(media_type="FILM", review_date="2024", score=5)
    media_factory(media_type="BOOK", review_date="2024", score=5)
    media_factory(media_type="FILM", review_date="2023", score=5)

    response = logged_in_client.get(
        reverse("stats_covers_htmx"), {"year": "2024", "type": "FILM", "page": "2"}, HTTP_HX_REQUEST="true"
    )

    assert "partials/stats/covers_page.html" in [t.name for t in response.templates]
    covers = response.context["covers"]
    assert covers.number == 2
    assert covers.paginator.count == STATS_COVERS_PER_PAGE + 1
    assert len(covers) == 1


def test_stats_covers_htmx_out_of_range_page_is_empty(logged_in_client, media_factory):
    """A page past the last one adds nothing, instead of repeating the covers already shown."""
    media_factory(score=5)

    response = logged_in_client.get(reverse("stats_covers_htmx"), {"page": "2"}, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert not response.content


@pytest.mark.parametrize(
    ("params", "message"),
    [({}, "No rated media yet."), ({"type": "GAME"}, "No rated media match the selected filters.")],
)
def test_stats_without_covers_message_depends_on_filters(logged_in_client, params, message):
    """Without covers, the message tells an empty collection apart from filters matching nothing."""
    response = logged_in_client.get(reverse("stats"), params)

    assert message in response.content.decode("utf-8")


def _home_count(client, url):
    """Number of media listed on the home page at `url`."""
    return client.get(url).context["page_obj"].paginator.count


def test_stats_year_bars_link_to_stats_of_that_year(logged_in_client, media_factory):
    """Each yearly bar links to the stats page filtered on that year, keeping the selected media type."""
    media_factory(media_type="BOOK", review_date="2016", score=7)
    media_factory(media_type="BOOK", review_date="2016-12-31", score=7)
    media_factory(media_type="FILM", review_date="2016-06-01", score=7)
    media_factory(media_type="BOOK", review_date="2017-01-01", score=7)

    bar = logged_in_client.get(reverse("stats"), {"type": "BOOK"}).context["per_year"][0]
    response = logged_in_client.get(bar["url"])

    assert bar["label"] == 2016
    assert (response.context["year"], response.context["media_type"]) == (2016, "BOOK")
    assert response.context["overview"]["count"] == bar["count"] == 2


def test_stats_month_bars_link_to_filtered_home(logged_in_client, media_factory):
    """Each monthly bar links to the media list filtered on that month."""
    media_factory(review_date="2024-02", score=7)
    media_factory(review_date="2024-02-29", score=7)
    media_factory(review_date="2024-03-01", score=7)

    response = logged_in_client.get(reverse("stats"), {"year": "2024"})

    february = response.context["per_month"][1]
    assert "review_from=2024-02-01" in february["url"]
    assert "review_to=2024-02-29" in february["url"]
    assert _home_count(logged_in_client, february["url"]) == february["count"] == 2


def test_stats_score_bars_link_to_filtered_home(logged_in_client, media_factory):
    """Each score bar links to the media list filtered on that score, keeping the selected year and type."""
    media_factory(media_type="GAME", review_date="2026-03", score=4)
    media_factory(media_type="GAME", review_date="2026", score=4)
    media_factory(media_type="GAME", review_date="2025-12-31", score=4)
    media_factory(media_type="FILM", review_date="2026-03", score=4)

    response = logged_in_client.get(reverse("stats"), {"year": "2026", "type": "GAME"})

    bar = response.context["score_distribution"][3]
    assert bar["label"] == 4
    assert _home_count(logged_in_client, bar["url"]) == bar["count"] == 2


def test_saved_view_save_stores_tag(logged_in_client, user, db):
    """The tag filter is stored with the saved view and restored in its URL."""
    tag = Tag.objects.create(name="Favourites")

    response = logged_in_client.post(reverse("saved_view_save"), {"view_name": "Tagged", "tag": str(tag.pk)})

    saved_view = SavedView.objects.get(user=user, name="Tagged")
    assert saved_view.filter_tag_id == tag.pk
    assert f"tag={tag.pk}" in response.url


def test_saved_view_rejects_nonexistent_tag(logged_in_client, user, db):
    """A saved view pointing to a missing tag is rejected."""
    logged_in_client.post(reverse("saved_view_save"), {"view_name": "Broken", "tag": "99999"})

    assert not SavedView.objects.filter(user=user, name="Broken").exists()


def test_save_view_modal_keeps_current_query_parameters(rf, user):
    """The save view form carries every non-empty query parameter, except the page."""
    request = rf.get("/", {"tag": "3", "search": "dune", "type": ["BOOK", "FILM"], "contributor": "", "page": "2"})
    request.user = user

    html = render_to_string("partials/saved_views/save_view_modal.html", request=request)

    for name, value in [("tag", "3"), ("search", "dune"), ("type", "BOOK"), ("type", "FILM")]:
        assert f'name="{name}" value="{value}"' in html
    assert 'name="page"' not in html
    assert 'name="contributor"' not in html


@pytest.mark.parametrize(("count", "label"), [(0, "0 items"), (1, "1 item"), (2, "2 items")])
def test_index_media_count_is_pluralized(logged_in_client, media_factory, count, label):
    """The media counter uses the singular form only for one item."""
    for _ in range(count):
        media_factory()

    response = logged_in_client.get(reverse("home"))

    assert re.search(rf"\b{label}\b(?!s)", response.content.decode())


def test_pages_declare_the_active_language(logged_in_client):
    """The html lang attribute follows the language of the request."""
    response = logged_in_client.get(reverse("home"), HTTP_ACCEPT_LANGUAGE="fr")

    assert '<html lang="fr">' in response.content.decode()


def test_backup_page_shows_each_message_once(logged_in_client, monkeypatch):
    """A message raised before the backup page is displayed only once, as a toast."""

    def failing_backup(*args, **kwargs):
        msg = "Disk full"
        raise OSError(msg)

    monkeypatch.setattr("core.views.create_backup", failing_backup)

    response = logged_in_client.get(reverse("backup_export"), follow=True)

    assert response.content.decode().count("Disk full") == 1


def test_saved_view_delete_asks_for_confirmation(logged_in_client, user):
    """Deleting a saved view from the sidebar asks for a confirmation first."""
    SavedView.objects.create(user=user, name="Old view")

    response = logged_in_client.get(reverse("home"))

    assert "hx-confirm" in response.content.decode()


def _back_url(response):
    """Return the target of the back link of a page, or None when it has none."""
    match = re.search(
        r'<a href="([^"]*)"\s+class="btn btn-ghost btn-sm btn-circle shrink-0"', response.content.decode()
    )
    return match and match.group(1)


def test_back_links_lead_to_the_parent_page(logged_in_client, media):
    """Back links go up the hierarchy: detail to list, edit to detail, import to edit or list."""
    home = reverse("home")
    detail = reverse("media_detail", args=[media.pk])
    edit = reverse("media_edit", args=[media.pk])

    assert _back_url(logged_in_client.get(detail)) == home
    assert _back_url(logged_in_client.get(edit)) == detail
    assert _back_url(logged_in_client.get(reverse("media_add"))) == home
    assert _back_url(logged_in_client.get(reverse("media_import"), {"media_id": media.pk})) == edit
    assert _back_url(logged_in_client.get(reverse("media_import"))) == home


@pytest.mark.parametrize("url_name", ["stats", "backup_manage", "accounts:profile_edit"])
def test_top_level_pages_have_no_back_link(logged_in_client, url_name):
    """Pages reached from the sidebar have no back link."""
    assert _back_url(logged_in_client.get(reverse(url_name))) is None


def test_import_page_title_depends_on_its_purpose(logged_in_client, media):
    """The import page is titled as adding a media, or as importing metadata into an existing one."""
    adding = logged_in_client.get(reverse("media_import")).content.decode()
    importing = logged_in_client.get(reverse("media_import"), {"media_id": media.pk}).content.decode()

    assert "Add media</h1>" in adding
    assert "Import metadata</h1>" in importing


def test_add_media_is_reachable_from_every_page(logged_in_client, media):
    """The add action is in the sidebar, and in a floating button on pages other than the forms."""
    add_url = reverse("media_import")
    detail = logged_in_client.get(reverse("media_detail", args=[media.pk])).content.decode()
    edit = logged_in_client.get(reverse("media_edit", args=[media.pk])).content.decode()

    assert detail.count(f'href="{add_url}"') == 2
    assert 'class="fab' in detail
    assert 'class="fab' not in edit


def test_sidebar_marks_the_current_saved_view(logged_in_client, user):
    """The saved view matching the current list is highlighted in the sidebar."""
    view = SavedView.objects.create(user=user, name="Games", filter_types=["GAME"])
    SavedView.objects.create(user=user, name="Books", filter_types=["BOOK"])

    content = logged_in_client.get(view.get_filter_url()).content.decode()

    assert re.search(rf'<a href="{re.escape(escape(view.get_filter_url()))}"\s+class="[^"]*menu-active', content)
    assert content.count("menu-active") == 1


def test_index_always_shows_the_grid(logged_in_client, media):
    """The list view is gone: an old URL asking for it shows the grid."""
    content = logged_in_client.get(reverse("home"), {"view_mode": "list"}).content.decode()

    assert 'id="media-container"' in content
    assert "<table" not in content


def _filter_form(content):
    """Return the HTML of the media filter form of a page."""
    start = content.index('<form id="media-filters"')
    return content[start : content.index("</form>", start)]


def test_sort_options_are_explicit_and_valid(logged_in_client):
    """The sort is chosen in one list of explicit options, each of which sorts the list as it says."""
    response = logged_in_client.get(reverse("home"), {"sort": "-score"})

    content = response.content.decode()
    assert re.search(r'name="sort"\s+value="-score"[^>]*\schecked', content)
    assert re.search(r'id="sort-label"[^>]*>\s*Best scores\s*<', content)
    for value, _label in response.context["sort_options"]:
        assert logged_in_client.get(reverse("home"), {"sort": value}).context["sort"] == value


def test_filter_form_holds_search_sort_and_filters(logged_in_client, agent):
    """Search, sort and filters belong to one form, so that none of them is lost when another changes."""
    form = _filter_form(logged_in_client.get(reverse("home"), {"contributor": agent.pk}).content.decode())

    for name in ["search", "sort", "type", "status", "score", "review_from", "has_review", "has_cover", "contributor"]:
        assert f'name="{name}"' in form


def test_filter_form_updates_the_page_in_place(logged_in_client):
    """The filter form updates the list and the parts of the page that depend on the filters, and the URL."""
    content = logged_in_client.get(reverse("home")).content.decode()
    form = _filter_form(content)

    assert 'hx-push-url="true"' in form
    target = re.search(r'hx-target="#([\w-]+)"', form).group(1)
    oob_ids = re.search(r'hx-select-oob="([^"]+)"', form).group(1).replace("#", "").split(",")
    for element_id in [target, *oob_ids]:
        assert f'id="{element_id}"' in content


def test_filter_toggles_show_the_selected_values(logged_in_client):
    """Selected filter values are shown as checked toggles."""
    content = logged_in_client.get(
        reverse("home"), {"type": "FILM", "status": "PAUSED", "score": "6", "has_review": "filled"}
    ).content.decode()

    for name, value in [("type", "FILM"), ("status", "PAUSED"), ("score", "6"), ("has_review", "filled")]:
        assert re.search(rf'name="{name}"\s+value="{value}"[^>]*\schecked', content)
    assert not re.search(r'name="type"\s+value="BOOK"[^>]*\schecked', content)


def test_filters_button_counts_the_active_filters(logged_in_client, agent):
    """The filters button shows how many filters are active, one per filter badge."""
    params = {"type": ["BOOK", "FILM"], "status": "PLANNED", "has_cover": "filled", "contributor": agent.pk}

    response = logged_in_client.get(reverse("home"), params)

    assert response.context["active_filter_count"] == 5
    assert re.search(r'id="filters-count"[^>]*>\s*5\s*<', response.content.decode())


def test_invalid_contributor_is_not_counted_as_a_filter(logged_in_client, db):
    """A contributor that does not exist filters nothing, and is not counted."""
    response = logged_in_client.get(reverse("home"), {"contributor": "99999"})

    assert response.context["active_filter_count"] == 0
