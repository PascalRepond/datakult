"""
Tests for core.views module.

These tests verify the behavior of views using pytest-django.
"""

from django.urls import reverse

from core.models import Agent, Media


class TestIndexView:
    """Tests for the index (home) view."""

    def test_index_requires_login(self, client):
        """The index view requires authentication."""
        url = reverse("home")
        response = client.get(url)

        assert response.status_code == 302
        assert "/login/" in response.url

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

    def test_media_add_requires_login(self, client):
        """The add media view requires authentication."""
        response = client.get(reverse("media_add"))

        assert response.status_code == 302

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

    def test_media_delete_requires_login(self, client, media):
        """The delete view requires authentication."""
        response = client.post(reverse("media_delete", kwargs={"pk": media.pk}))

        assert response.status_code == 302
        assert "/login/" in response.url

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

    def test_search_requires_login(self, client):
        """The search view requires authentication."""
        response = client.get(reverse("search"))

        assert response.status_code == 302

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

    def test_agent_search_requires_login(self, client):
        """The agent search view requires authentication."""
        response = client.get(reverse("agent_search_htmx"))

        assert response.status_code == 302

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

    def test_agent_select_requires_login(self, client):
        """The agent select view requires authentication."""
        response = client.post(reverse("agent_select_htmx"))

        assert response.status_code == 302

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
