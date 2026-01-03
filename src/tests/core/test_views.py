"""
Tests for core.views module.

These tests verify the behavior of views using pytest-django.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from core.models import Agent, Media
from core.utils import create_backup


class TestIndexView:
    """Tests for the index (home) view."""

    def test_index_accessible_when_logged_in(self, logged_in_client):
        """The index view is accessible when logged in."""
        response = logged_in_client.get(reverse("home"))

        assert response.status_code == 200

    def test_index_displays_media_list(self, logged_in_client, media):
        """The index view displays the media list."""
        response = logged_in_client.get(reverse("home"))

        assert response.status_code == 200
        assert "media_list" in response.context

    def test_index_htmx_request_returns_partial(self, logged_in_client, media):
        """HTMX requests return the partial template."""
        response = logged_in_client.get(
            reverse("home"),
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        # Should use the partial template, not the full page
        assert "partials/media-list.html" in [t.name for t in response.templates]


class TestMediaEditView:
    """Tests for the media_edit view."""

    def test_media_add_get_displays_form(self, logged_in_client):
        """GET request displays the form."""
        response = logged_in_client.get(reverse("media_add"))

        assert response.status_code == 200
        assert "form" in response.context

    def test_media_add_post_creates_media(self, logged_in_client, db):
        """POST with valid data creates a new media."""
        data = {
            "title": "New Test Media",
            "media_type": "BOOK",
            "status": "PLANNED",
        }
        response = logged_in_client.post(reverse("media_add"), data)

        assert response.status_code == 302  # Redirect after success
        assert Media.objects.filter(title="New Test Media").exists()

    def test_media_add_with_new_contributor(self, logged_in_client, db):
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

    def test_media_edit_get_displays_existing(self, logged_in_client, media):
        """GET on edit view shows the existing media."""
        response = logged_in_client.get(reverse("media_edit", kwargs={"pk": media.pk}))

        assert response.status_code == 200
        assert response.context["media"] == media

    def test_media_edit_post_updates_media(self, logged_in_client, media):
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

    def test_media_edit_removes_contributor_cleans_orphan(self, logged_in_client, db):
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


class TestMediaDeleteView:
    """Tests for the media_delete view."""

    def test_media_delete_post_deletes_media(self, logged_in_client, media):
        """POST request deletes the media."""
        media_pk = media.pk
        response = logged_in_client.post(reverse("media_delete", kwargs={"pk": media_pk}))

        assert response.status_code == 302
        assert not Media.objects.filter(pk=media_pk).exists()

    def test_media_delete_cleans_orphan_contributors(self, logged_in_client, db):
        """Deleting media removes orphan contributors."""
        agent = Agent.objects.create(name="Will Be Orphan")
        media = Media.objects.create(title="To Delete", media_type="BOOK")
        media.contributors.add(agent)

        logged_in_client.post(reverse("media_delete", kwargs={"pk": media.pk}))

        assert not Agent.objects.filter(pk=agent.pk).exists()

    def test_media_delete_keeps_shared_contributors(self, logged_in_client, db):
        """Contributors linked to other media are kept."""
        agent = Agent.objects.create(name="Shared Author")
        media1 = Media.objects.create(title="To Delete", media_type="BOOK")
        media2 = Media.objects.create(title="To Keep", media_type="BOOK")
        media1.contributors.add(agent)
        media2.contributors.add(agent)

        logged_in_client.post(reverse("media_delete", kwargs={"pk": media1.pk}))

        assert Agent.objects.filter(pk=agent.pk).exists()

    def test_media_delete_get_redirects(self, logged_in_client, media):
        """GET request redirects to edit page (no delete)."""
        response = logged_in_client.get(reverse("media_delete", kwargs={"pk": media.pk}))

        assert response.status_code == 302
        assert f"/media/{media.pk}/edit/" in response.url
        assert Media.objects.filter(pk=media.pk).exists()


class TestSearchView:
    """Tests for the search view."""

    def test_search_with_query(self, logged_in_client, media):
        """Search returns results matching the query."""
        response = logged_in_client.get(reverse("search"), {"search": media.title})

        assert response.status_code == 200

    def test_search_by_title(self, logged_in_client, media_factory):
        """Search finds media by title."""
        media_factory(title="Unique Title Here")
        media_factory(title="Other Book")

        response = logged_in_client.get(reverse("search"), {"search": "Unique"})

        assert len(response.context["media_list"]) == 1

    def test_search_by_contributor(self, logged_in_client, db):
        """Search finds media by contributor name."""
        agent = Agent.objects.create(name="Famous Author")
        media = Media.objects.create(title="Some Book", media_type="BOOK")
        media.contributors.add(agent)

        response = logged_in_client.get(reverse("search"), {"search": "Famous"})

        assert media in response.context["media_list"]


class TestAgentSearchHtmxView:
    """Tests for the agent_search_htmx view."""

    def test_agent_search_returns_matching_agents(self, logged_in_client, db):
        """Search returns agents matching the query."""
        Agent.objects.create(name="John Doe")
        Agent.objects.create(name="Jane Doe")
        Agent.objects.create(name="Bob Smith")

        response = logged_in_client.get(reverse("agent_search_htmx"), {"q": "Doe"})

        assert response.status_code == 200
        assert len(response.context["agents"]) == 2

    def test_agent_search_empty_query(self, logged_in_client, agent):
        """Empty query returns no agents."""
        response = logged_in_client.get(reverse("agent_search_htmx"), {"q": ""})

        assert response.status_code == 200
        assert len(response.context["agents"]) == 0

    def test_agent_search_limits_results(self, logged_in_client, db):
        """Search limits results to 12."""
        for i in range(20):
            Agent.objects.create(name=f"Agent {i}")

        response = logged_in_client.get(reverse("agent_search_htmx"), {"q": "Agent"})

        assert len(response.context["agents"]) == 12


class TestAgentSelectHtmxView:
    """Tests for the agent_select_htmx view."""

    def test_agent_select_returns_chip(self, logged_in_client, agent):
        """Selecting an agent returns the chip template."""
        response = logged_in_client.post(
            reverse("agent_select_htmx"),
            {"id": agent.pk},
        )

        assert response.status_code == 200
        assert response.context["agent"] == agent

    def test_agent_select_nonexistent(self, logged_in_client, db):
        """Selecting a non-existent agent returns error."""
        response = logged_in_client.post(
            reverse("agent_select_htmx"),
            {"id": 99999},
        )

        assert response.status_code == 200
        assert response.context["error"] == "Agent not found"


class TestSortingHelper:
    """Tests for the _resolve_sorting helper logic via index view."""

    def test_default_sorting(self, logged_in_client):
        """Default sorting is by created_at descending."""
        response = logged_in_client.get(reverse("home"))

        assert response.context["sort_field"] == "created_at"
        assert response.context["order_by"] == "-created_at"

    def test_custom_sorting(self, logged_in_client):
        """Custom sorting is applied."""
        response = logged_in_client.get(reverse("home"), {"sort": "score"})

        assert response.context["sort_field"] == "score"
        assert response.context["order_by"] == "score"

    def test_descending_sorting(self, logged_in_client):
        """Descending sorting is applied."""
        response = logged_in_client.get(reverse("home"), {"sort": "-review_date"})

        assert response.context["sort_field"] == "review_date"
        assert response.context["order_by"] == "-review_date"

    def test_invalid_sort_field_uses_default(self, logged_in_client):
        """Invalid sort field falls back to default."""
        response = logged_in_client.get(reverse("home"), {"sort": "invalid_field"})

        assert response.context["sort_field"] == "created_at"


class TestFilteringHelper:
    """Tests for the filtering logic via index view."""

    def test_filter_by_type(self, logged_in_client, media_factory):
        """Filtering by media type works."""
        media_factory(title="A Book", media_type="BOOK")
        media_factory(title="A Film", media_type="FILM")

        response = logged_in_client.get(reverse("home"), {"type": "BOOK"})

        titles = [m.title for m in response.context["media_list"]]
        assert "A Book" in titles
        assert "A Film" not in titles

    def test_filter_by_status(self, logged_in_client, media_factory):
        """Filtering by status works."""
        media_factory(title="Planned", status="PLANNED")
        media_factory(title="Completed", status="COMPLETED")

        response = logged_in_client.get(reverse("home"), {"status": "COMPLETED"})

        titles = [m.title for m in response.context["media_list"]]
        assert "Completed" in titles
        assert "Planned" not in titles

    def test_filter_by_contributor(self, logged_in_client, db):
        """Filtering by contributor works."""
        agent = Agent.objects.create(name="Specific Author")
        media = Media.objects.create(title="By Author", media_type="BOOK")
        media.contributors.add(agent)
        Media.objects.create(title="No Author", media_type="BOOK")

        response = logged_in_client.get(reverse("home"), {"contributor": agent.pk})

        titles = [m.title for m in response.context["media_list"]]
        assert "By Author" in titles
        assert "No Author" not in titles

    def test_filter_by_no_score(self, logged_in_client, media_factory):
        """Filtering by 'no score' works."""
        media_factory(title="Rated", score=8)
        media_factory(title="Unrated", score=None)

        response = logged_in_client.get(reverse("home"), {"score": "none"})

        titles = [m.title for m in response.context["media_list"]]
        assert "Unrated" in titles
        assert "Rated" not in titles


class TestMediaReviewHtmxViews:
    """Tests for HTMX views that display media reviews."""

    def test_media_review_clamped_returns_partial(self, logged_in_client, db):
        """Clamped review view returns the clamped partial template."""
        media = Media.objects.create(
            title="Test Media",
            media_type="BOOK",
            review="This is a test review with some content that could be truncated.",
        )
        response = logged_in_client.get(reverse("media_review_clamped_htmx", kwargs={"pk": media.pk}))

        assert response.status_code == 200
        assert "partials/media-review-clamped.html" in [t.name for t in response.templates]
        assert "media" in response.context
        assert response.context["media"] == media

    def test_media_review_clamped_with_short_review(self, logged_in_client, db):
        """Clamped review with short text doesn't show 'See more' button."""
        media = Media.objects.create(
            title="Test Media",
            media_type="BOOK",
            review="Short review",
        )
        response = logged_in_client.get(reverse("media_review_clamped_htmx", kwargs={"pk": media.pk}))

        content = response.content.decode("utf-8")
        # With less than 50 words, the 'See more' button should not appear
        assert "See more" not in content

    def test_media_review_clamped_with_long_review(self, logged_in_client, db):
        """Clamped review with long text shows 'See more' button."""
        long_review = " ".join(["word"] * 55)
        media = Media.objects.create(
            title="Test Media",
            media_type="BOOK",
            review=long_review,
        )
        response = logged_in_client.get(reverse("media_review_clamped_htmx", kwargs={"pk": media.pk}))

        content = response.content.decode("utf-8")
        # With more than 50 words, the 'See more' button should appear
        assert "See more" in content

    def test_media_review_full_returns_partial(self, logged_in_client, db):
        """Full review view returns the full partial template."""
        media = Media.objects.create(
            title="Test Media",
            media_type="BOOK",
            review="This is a test review.",
        )
        response = logged_in_client.get(reverse("media_review_full_htmx", kwargs={"pk": media.pk}))

        assert response.status_code == 200
        assert "partials/media-review-full.html" in [t.name for t in response.templates]
        assert "media" in response.context
        assert response.context["media"] == media

    def test_media_review_full_shows_see_less_button(self, logged_in_client, db):
        """Full review view shows 'See less' button."""
        media = Media.objects.create(
            title="Test Media",
            media_type="BOOK",
            review="Some review content",
        )
        response = logged_in_client.get(reverse("media_review_full_htmx", kwargs={"pk": media.pk}))

        content = response.content.decode("utf-8")
        assert "See less" in content

    def test_media_review_renders_html_safely(self, logged_in_client, db):
        """Review views render HTML content from review_rendered field."""
        media = Media.objects.create(
            title="Test Media",
            media_type="BOOK",
            review="**Bold text**",
        )
        # After save, review_rendered should contain HTML
        media.refresh_from_db()

        response = logged_in_client.get(reverse("media_review_full_htmx", kwargs={"pk": media.pk}))
        content = response.content.decode("utf-8")

        # The rendered HTML should be present in the response
        assert "<strong>Bold text</strong>" in content

    def test_media_review_nonexistent_media_returns_404(self, logged_in_client):
        """Accessing review views with nonexistent media returns 404."""
        response_clamped = logged_in_client.get(reverse("media_review_clamped_htmx", kwargs={"pk": 99999}))
        response_full = logged_in_client.get(reverse("media_review_full_htmx", kwargs={"pk": 99999}))

        assert response_clamped.status_code == 404
        assert response_full.status_code == 404


class TestBackupManageView:
    """Tests for the backup_manage view."""

    def test_backup_manage_displays_page(self, logged_in_client):
        """The backup manage view displays the backup management page."""
        response = logged_in_client.get(reverse("backup_manage"))

        assert response.status_code == 200
        assert "backup_manage.html" in [t.name for t in response.templates]


class TestBackupExportView:
    """Tests for the backup_export view."""

    def test_backup_export_creates_and_downloads_backup(self, logged_in_client, db):
        """The backup export view creates and returns a backup file."""
        # Create some test data
        Media.objects.create(title="Test Media", media_type="BOOK")

        response = logged_in_client.get(reverse("backup_export"))

        # Should return a file download
        assert response.status_code == 200
        # Django's FileResponse detects .tar.gz as gzip
        assert response["Content-Type"] == "application/gzip"
        assert "attachment" in response["Content-Disposition"]
        assert "datakult_backup_" in response["Content-Disposition"]

    def test_backup_export_handles_errors_gracefully(self, logged_in_client, monkeypatch):
        """The backup export view handles errors and redirects with message."""

        # Mock create_backup to raise an exception
        def mock_create_backup(*args, **kwargs):
            msg = "Test error"
            raise OSError(msg)

        monkeypatch.setattr("core.views.create_backup", mock_create_backup)

        response = logged_in_client.get(reverse("backup_export"))

        # Should redirect back to backup manage with error message
        assert response.status_code == 302
        assert response.url == reverse("backup_manage")


class TestBackupImportView:
    """Tests for the backup_import view."""

    def test_backup_import_get_redirects(self, logged_in_client):
        """GET requests to backup import redirect to backup manage."""
        response = logged_in_client.get(reverse("backup_import"))

        assert response.status_code == 302
        assert response.url == reverse("backup_manage")

    def test_backup_import_requires_file(self, logged_in_client):
        """The backup import view requires a file to be uploaded."""
        response = logged_in_client.post(reverse("backup_import"))

        assert response.status_code == 302
        # Should redirect back with error message

    def test_backup_import_rejects_invalid_format(self, logged_in_client):
        """The backup import view rejects files with invalid format."""
        invalid_file = SimpleUploadedFile("backup.txt", b"not a backup", content_type="text/plain")

        response = logged_in_client.post(reverse("backup_import"), {"backup_file": invalid_file})

        assert response.status_code == 302
        assert response.url == reverse("backup_manage")

    def test_backup_import_restores_data(self, logged_in_client, db):
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
                uploaded_file = SimpleUploadedFile(
                    backup_path.name, backup_file.read(), content_type="application/x-tar"
                )
                response = logged_in_client.post(reverse("backup_import"), {"backup_file": uploaded_file})

            # Should redirect to home
            assert response.status_code == 302
            assert response.url == reverse("home")

            # Data should be restored
            assert Media.objects.count() == 1
            restored_media = Media.objects.first()
            assert restored_media.title == original_media.title
            assert restored_media.status == original_media.status

    def test_backup_import_handles_errors(self, logged_in_client):
        """The backup import view handles errors gracefully."""
        # Create a valid tar.gz file with invalid content
        invalid_file = SimpleUploadedFile("backup.tar.gz", b"invalid content", content_type="application/x-tar")

        response = logged_in_client.post(reverse("backup_import"), {"backup_file": invalid_file})

        # Should redirect back to backup manage with error message
        assert response.status_code == 302
        assert response.url == reverse("backup_manage")


class TestPaginationBehavior:
    """Tests for pagination behavior across views."""

    def test_index_paginates_results(self, logged_in_client, media_factory):
        """Index view paginates results with 20 items per page."""
        # Create 25 media items
        for i in range(25):
            media_factory(title=f"Media {i}")

        response = logged_in_client.get(reverse("home"))

        assert response.status_code == 200
        assert "page_obj" in response.context
        assert len(response.context["media_list"]) == 20
        assert response.context["page_obj"].has_next()

    def test_index_second_page_shows_remaining_items(self, logged_in_client, media_factory):
        """Index view shows remaining items on second page."""
        # Create 25 media items
        for i in range(25):
            media_factory(title=f"Media {i}")

        response = logged_in_client.get(reverse("home"), {"page": 2})

        assert response.status_code == 200
        assert len(response.context["media_list"]) == 5
        assert response.context["page_obj"].has_previous()
        assert not response.context["page_obj"].has_next()

    def test_search_paginates_results(self, logged_in_client, media_factory):
        """Search view paginates results."""
        # Create 25 media items with searchable title
        for i in range(25):
            media_factory(title=f"Searchable {i}")

        response = logged_in_client.get(reverse("search"), {"search": "Searchable"})

        assert response.status_code == 200
        assert len(response.context["media_list"]) == 20
        assert response.context["page_obj"].has_next()


class TestLoadMoreMediaView:
    """Tests for the load_more_media view (infinite scroll / lazy-loading)."""

    def test_load_more_returns_partial_template(self, logged_in_client, media_factory):
        """Load more view returns the media-items-page partial template."""
        for i in range(25):
            media_factory(title=f"Media {i}")

        response = logged_in_client.get(reverse("load_more_media"), {"page": 2})

        assert response.status_code == 200
        assert "partials/media-items-page.html" in [t.name for t in response.templates]

    def test_load_more_returns_next_page_items(self, logged_in_client, media_factory):
        """Load more view returns items for the requested page."""
        # Create 25 items
        for i in range(25):
            media_factory(title=f"Media {i:02d}")

        # Request page 2 (items 21-25)
        response = logged_in_client.get(reverse("load_more_media"), {"page": 2})

        assert response.status_code == 200
        assert len(response.context["media_list"]) == 5

    def test_load_more_preserves_sorting(self, logged_in_client, media_factory):
        """Load more view preserves sort order from initial request."""
        media_factory(title="A", score=5)
        media_factory(title="B", score=8)
        media_factory(title="C", score=3)

        response = logged_in_client.get(reverse("load_more_media"), {"page": 1, "sort": "score"})

        assert response.status_code == 200
        scores = [m.score for m in response.context["media_list"] if m.score is not None]
        # Should be sorted ascending by score
        assert scores == sorted(scores)

    def test_load_more_preserves_filters(self, logged_in_client, media_factory):
        """Load more view preserves filters from initial request."""
        media_factory(title="Book 1", media_type="BOOK")
        media_factory(title="Film 1", media_type="FILM")
        media_factory(title="Book 2", media_type="BOOK")

        response = logged_in_client.get(reverse("load_more_media"), {"page": 1, "type": "BOOK"})

        assert response.status_code == 200
        media_types = [m.media_type for m in response.context["media_list"]]
        assert all(mt == "BOOK" for mt in media_types)

    def test_load_more_with_search_query(self, logged_in_client, media_factory):
        """Load more view applies search query when provided."""
        media_factory(title="Python Guide")
        media_factory(title="JavaScript Guide")
        media_factory(title="Python Cookbook")

        response = logged_in_client.get(reverse("load_more_media"), {"page": 1, "search": "Python"})

        assert response.status_code == 200
        assert len(response.context["media_list"]) == 2
        titles = [m.title for m in response.context["media_list"]]
        assert all("Python" in title for title in titles)

    def test_load_more_page_obj_has_next_when_more_pages(self, logged_in_client, media_factory):
        """Load more view sets has_next correctly when more pages exist."""
        # Create 45 items (3 pages)
        for i in range(45):
            media_factory(title=f"Media {i}")

        response = logged_in_client.get(reverse("load_more_media"), {"page": 2})

        assert response.status_code == 200
        assert response.context["page_obj"].has_next()
        assert response.context["page_obj"].number == 2

    def test_load_more_page_obj_no_next_on_last_page(self, logged_in_client, media_factory):
        """Load more view sets has_next to False on last page."""
        # Create 25 items (2 pages)
        for i in range(25):
            media_factory(title=f"Media {i}")

        response = logged_in_client.get(reverse("load_more_media"), {"page": 2})

        assert response.status_code == 200
        assert not response.context["page_obj"].has_next()
        assert response.context["page_obj"].number == 2

    def test_load_more_includes_view_mode_in_context(self, logged_in_client, media_factory):
        """Load more view includes view_mode in context for template rendering."""
        media_factory(title="Test")

        response_list = logged_in_client.get(reverse("load_more_media"), {"page": 1, "view_mode": "list"})
        response_grid = logged_in_client.get(reverse("load_more_media"), {"page": 1, "view_mode": "grid"})

        assert response_list.context["view_mode"] == "list"
        assert response_grid.context["view_mode"] == "grid"
