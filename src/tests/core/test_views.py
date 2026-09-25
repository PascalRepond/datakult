"""
Tests for core.views module.

These tests verify the behavior of views using pytest-django.
"""

import logging
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import escape
from freezegun import freeze_time
from PIL import Image

from accounts import urls as accounts_urls
from core import urls as core_urls
from core.models import Agent, Media, MediaType, SavedView, Tag
from core.utils import create_backup
from core.views import IMPORT_SEARCHES, STATS_COVERS_PER_PAGE
from tests.helpers import image_bytes, media_form_data, messages_of, titles


def _app_urls():
    """Every URL name of the core and accounts apps, with the primary key it may take."""
    for prefix, patterns in [("", core_urls.urlpatterns), ("accounts:", accounts_urls.urlpatterns)]:
        for pattern in patterns:
            kwargs = {"pk": 1} if "<int:pk>" in str(pattern.pattern) else {}
            yield pytest.param(prefix + pattern.name, kwargs, id=prefix + pattern.name)


@pytest.mark.parametrize(("url_name", "kwargs"), list(_app_urls()))
def test_every_page_requires_login(client, db, url_name, kwargs):
    """Every page and endpoint of the app redirects anonymous users to the login page."""
    response = client.post(reverse(url_name, kwargs=kwargs))

    assert response.status_code == 302
    assert response.url.startswith(reverse("login"))


# Media list


def test_index_fills_cover_frames_with_their_colour(logged_in_client, media_factory):
    """The colour of a cover fills the space left around it in its card."""
    media_factory(media_type="MUSIC", cover="covers/cover.jpg", cover_color="#333333")

    response = logged_in_client.get(reverse("home"))

    assert 'style="--cover-color: #333333"' in response.content.decode()


@pytest.mark.parametrize("query", ["Unique", "Famous", "spicy", "Desert", "1965"])
def test_search_matches_titles_contributors_reviews_tags_and_years(logged_in_client, media_factory, query):
    """A search finds media by title, contributor, review, tag or publication year."""
    media_factory(
        title="Unique Title",
        pub_year=1965,
        review="A spicy tale",
        contributors=[Agent.objects.create(name="Famous Author")],
        tags=[Tag.objects.create(name="Desert")],
    )
    media_factory(title="Other Book")

    response = logged_in_client.get(reverse("home"), {"search": query})

    assert titles(response) == ["Unique Title"]


@pytest.mark.parametrize("params", [{}, {"sort": "invalid_field"}, {"sort": "-updated_at"}, {"sort": "created_at"}])
def test_sort_outside_the_options_uses_default(logged_in_client, params):
    """Without a sort, or with one that is not a sort option, such as a removed one, the list sorts by review date."""
    response = logged_in_client.get(reverse("home"), params)

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

    assert titles(response) == expected


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


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"type": "BOOK"}, ["Planned book"]),
        ({"status": "COMPLETED"}, ["Rated film"]),
        ({"score": "none"}, ["Planned book"]),
    ],
)
def test_filters_keep_the_matching_media(logged_in_client, media_factory, params, expected):
    """The type, status and score filters keep the media that match them, 'none' standing for unrated media."""
    media_factory(title="Planned book", media_type="BOOK", status="PLANNED")
    media_factory(title="Rated film", media_type="FILM", status="COMPLETED", score=8)

    response = logged_in_client.get(reverse("home"), params)

    assert titles(response) == expected


def test_filter_by_contributor(logged_in_client, media, media_factory, agent):
    """The contributor filter keeps the media of that contributor."""
    media_factory(title="No Author")

    response = logged_in_client.get(reverse("home"), {"contributor": agent.pk})

    assert titles(response) == [media.title]


def test_filter_with_invalid_date_ignores_filter(logged_in_client, media_factory):
    """Invalid date values in URL are silently ignored."""
    media_factory(title="Recent", review_date="2025-01-01")
    media_factory(title="Old", review_date="2020-01-01")

    response = logged_in_client.get(reverse("home"), {"review_from": "not-a-date"})

    assert titles(response) == ["Recent", "Old"]


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

    assert set(titles(from_new_year)) == {"Year", "January", "March", "March 2nd"}
    assert set(titles(from_march)) == {"March", "March 2nd"}
    assert set(titles(from_march_2nd)) == {"March 2nd"}


def test_media_review_modal_shows_the_full_review(logged_in_client, media_factory):
    """The review modal shows the whole rendered review, with links to edit the media and to its page."""
    media = media_factory(review="**Bold text** " + "word " * 80, score=8)

    response = logged_in_client.get(reverse("media_review_htmx", kwargs={"pk": media.pk}))
    content = response.content.decode()

    assert "<strong>Bold text</strong>" in content
    assert content.count("word") == 80
    assert f'href="{reverse("media_edit", args=[media.pk])}"' in content
    assert f'href="{reverse("media_detail", args=[media.pk])}"' in content


def test_media_review_modal_of_missing_media_returns_404(logged_in_client):
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


def test_empty_library_invites_to_add_a_first_media(logged_in_client):
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


def test_index_paginates_results_across_pages(logged_in_client, media_factory):
    """Index view paginates results with 20 items per page and navigates correctly."""
    for i in range(25):
        media_factory(title=f"Media {i}")

    page1 = logged_in_client.get(reverse("home"))
    page2 = logged_in_client.get(reverse("home"), {"page": 2})

    assert len(page1.context["media_list"]) == 20
    assert page1.context["page_obj"].has_next()
    assert len(page2.context["media_list"]) == 5
    assert not page2.context["page_obj"].has_next()


def test_load_more_returns_the_next_page_as_a_partial(logged_in_client, media_factory):
    """Load more returns the items of the requested page, without the rest of the page."""
    for i in range(25):
        media_factory(title=f"Media {i}")

    response = logged_in_client.get(reverse("load_more_media"), {"page": 2})

    assert "partials/media_items/media_list_page.html" in [t.name for t in response.templates]
    assert "base/base.html" not in [t.name for t in response.templates]
    assert len(response.context["media_list"]) == 5


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"sort": "score"}, ["Python C", "Python A", "Film B"]),
        ({"type": "FILM"}, ["Film B"]),
        ({"search": "Python"}, ["Python C", "Python A"]),
    ],
)
def test_load_more_keeps_the_sort_filters_and_search(logged_in_client, media_factory, params, expected):
    """Load more sorts, filters and searches the next items as the list they follow."""
    media_factory(title="Python A", score=5, review_date="2024-01")
    media_factory(title="Film B", media_type="FILM", score=8, review_date="2024-02")
    media_factory(title="Python C", score=3, review_date="2024-03")

    response = logged_in_client.get(reverse("load_more_media"), {"page": 1, **params})

    assert titles(response) == expected


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


def test_invalid_contributor_is_not_counted_as_a_filter(logged_in_client):
    """A contributor that does not exist filters nothing, and is not counted."""
    response = logged_in_client.get(reverse("home"), {"contributor": "99999"})

    assert response.context["active_filter_count"] == 0


def test_media_card_links_to_its_edit_form(logged_in_client, media):
    """Each card of the list links straight to the edit form of its media."""
    content = logged_in_client.get(reverse("home")).content.decode()

    assert f'href="{reverse("media_edit", args=[media.pk])}"' in content


def test_media_card_shows_its_score_but_not_its_status(rf, media_factory):
    """A card shows the score and verdict of its media, and leaves its status to the media page."""
    media = media_factory(status="PAUSED", score=8)

    html = render_to_string("partials/media_items/media_item.html", {"media_list": [media], "request": rf.get("/")})

    assert media.get_score_display() in html
    assert media.get_status_display() not in html


# Media add, edit and delete


def test_media_add_creates_media_and_confirms_it(logged_in_client):
    """Adding a media creates it, then shows it with a message naming it."""
    response = logged_in_client.post(reverse("media_add"), media_form_data(title="New Test Media"))

    media = Media.objects.get(title="New Test Media")
    assert response.url == reverse("media_detail", args=[media.pk])
    assert messages_of(response) == ["'New Test Media' created successfully"]


def test_media_add_with_new_contributor(logged_in_client):
    """POST with new_contributors creates agents and links them."""
    logged_in_client.post(reverse("media_add"), media_form_data(new_contributors=["New Author"]))

    assert list(Media.objects.get().contributors.values_list("name", flat=True)) == ["New Author"]


def test_media_edit_updates_media_and_confirms_it(logged_in_client, media):
    """Editing a media updates it, then shows it with a message naming it."""
    response = logged_in_client.post(
        reverse("media_edit", kwargs={"pk": media.pk}), media_form_data(title="Updated Title", status="COMPLETED")
    )

    media.refresh_from_db()
    assert (media.title, media.status) == ("Updated Title", "COMPLETED")
    assert response.url == reverse("media_detail", args=[media.pk])
    assert messages_of(response) == ["'Updated Title' updated successfully"]


def test_media_edit_removes_contributor_cleans_orphan(logged_in_client, media, agent):
    """Removing a contributor from media deletes orphan agent."""
    logged_in_client.post(reverse("media_edit", kwargs={"pk": media.pk}), media_form_data(contributors=[]))

    assert not Agent.objects.filter(pk=agent.pk).exists()


def test_media_edit_import_cover_is_compressed_with_its_colour(logged_in_client, media, cover_png, monkeypatch):
    """A cover imported from an external source is compressed like an uploaded one, and keeps its colour."""
    monkeypatch.setattr("core.views._download_cover", lambda _url: cover_png)
    data = media_form_data(import_cover_url="https://image.tmdb.org/t/p/w500/cover.jpg")

    logged_in_client.post(reverse("media_edit", kwargs={"pk": media.pk}), data)

    media.refresh_from_db()
    with Image.open(media.cover.path) as cover:
        assert cover.format == "JPEG"
    assert media.cover_color == "#333333"


@pytest.mark.parametrize("imported", [False, True])
def test_media_edit_reports_cover_that_cannot_be_compressed(logged_in_client, media, monkeypatch, imported):
    """A cover in a format that cannot be compressed, uploaded or imported, is reported on the form."""
    tiff = image_bytes((400, 600), fmt="TIFF")
    data = media_form_data()
    if imported:
        monkeypatch.setattr("core.views._download_cover", lambda _url: tiff)
        data["import_cover_url"] = "https://image.tmdb.org/t/p/w500/cover.jpg"
    else:
        data["cover"] = SimpleUploadedFile("cover.tiff", tiff)

    response = logged_in_client.post(reverse("media_edit", kwargs={"pk": media.pk}), data)

    assert response.context["form"].has_error("cover")
    media.refresh_from_db()
    assert not media.cover


def test_media_delete_deletes_media_and_confirms_it(logged_in_client, media):
    """Deleting a media removes it, then goes back to the list with a message naming it."""
    response = logged_in_client.post(reverse("media_delete", kwargs={"pk": media.pk}))

    assert not Media.objects.filter(pk=media.pk).exists()
    assert response.url == reverse("home")
    assert messages_of(response) == ["'Test Media' deleted successfully"]


def test_media_delete_cleans_orphan_contributors(logged_in_client, media, agent):
    """Deleting media removes orphan contributors."""
    logged_in_client.post(reverse("media_delete", kwargs={"pk": media.pk}))

    assert not Agent.objects.filter(pk=agent.pk).exists()


def test_media_delete_keeps_shared_contributors(logged_in_client, media, media_factory, agent):
    """Contributors linked to other media are kept."""
    media_factory(title="To Keep", contributors=[agent])

    logged_in_client.post(reverse("media_delete", kwargs={"pk": media.pk}))

    assert Agent.objects.filter(pk=agent.pk).exists()


def test_media_delete_get_redirects(logged_in_client, media):
    """GET request redirects to edit page (no delete)."""
    response = logged_in_client.get(reverse("media_delete", kwargs={"pk": media.pk}))

    assert response.url == reverse("media_edit", args=[media.pk])
    assert Media.objects.filter(pk=media.pk).exists()


def test_edit_form_starts_with_title_and_type(logged_in_client, media):
    """The title and the media type, the two required fields, come first in the edit form."""
    content = logged_in_client.get(reverse("media_edit", args=[media.pk])).content.decode()

    assert content.index('name="title"') < content.index('name="cover"')
    assert content.index('name="media_type"') < content.index('name="cover"')


@pytest.mark.parametrize("editing", [True, False])
def test_edit_form_actions_lead_back_to_where_it_came_from(logged_in_client, media, editing):
    """The action bar saves the form, or cancels back to the media page, or to the list for a new media."""
    url = reverse("media_edit", args=[media.pk]) if editing else reverse("media_add")
    content = logged_in_client.get(url).content.decode()
    back = reverse("media_detail", args=[media.pk]) if editing else reverse("home")

    bar = content[content.index('id="form-actions"') :]
    assert re.search(rf'href="{back}"[^>]*>\s*Cancel', bar)
    assert 'type="submit"' in bar
    assert ('for="confirm-delete-modal"' in bar) is editing


def test_today_button_is_not_inside_a_label(logged_in_client, media):
    """The button setting the review date to today is not nested in the label of the field."""
    content = logged_in_client.get(reverse("media_edit", args=[media.pk])).content.decode()

    assert not re.search(r"<label(?:(?!</label>)[\s\S])*set-today-btn", content)


def test_edit_form_has_the_anchors_of_the_invites(logged_in_client, media):
    """The edit form has the anchors that the invites of the media page lead to."""
    content = logged_in_client.get(reverse("media_edit", args=[media.pk])).content.decode()

    assert 'id="score-field"' in content
    assert 'id="review-field"' in content


# Contributors and tags


def test_agent_search_returns_matching_agents(logged_in_client, db):
    """Search returns agents matching the query."""
    for name in ["John Doe", "Jane Doe", "Bob Smith"]:
        Agent.objects.create(name=name)

    response = logged_in_client.get(reverse("agent_search_htmx"), {"q": "Doe"})

    assert [agent.name for agent in response.context["agents"]] == ["Jane Doe", "John Doe"]


def test_agent_search_empty_query(logged_in_client, agent):
    """Empty query returns no agents."""
    response = logged_in_client.get(reverse("agent_search_htmx"), {"q": ""})

    assert len(response.context["agents"]) == 0


def test_agent_search_limits_results(logged_in_client, db):
    """Search limits results to 12."""
    Agent.objects.bulk_create(Agent(name=f"Agent {i}") for i in range(20))

    response = logged_in_client.get(reverse("agent_search_htmx"), {"q": "Agent"})

    assert len(response.context["agents"]) == 12


def test_agent_select_returns_chip(logged_in_client, agent):
    """Selecting an agent returns the chip template."""
    response = logged_in_client.post(reverse("agent_select_htmx"), {"id": agent.pk})

    assert response.context["agent"] == agent


def test_agent_select_nonexistent(logged_in_client, db):
    """Selecting a non-existent agent returns error."""
    response = logged_in_client.post(reverse("agent_select_htmx"), {"id": 99999})

    assert response.context["error"] == "Agent not found"


# Media detail


def test_media_detail_nonexistent_returns_404(logged_in_client):
    """Accessing detail view with nonexistent media returns 404."""
    response = logged_in_client.get(reverse("media_detail", kwargs={"pk": 99999}))

    assert response.status_code == 404


def test_media_detail_shows_all_fields(logged_in_client, media_factory, agent):
    """The detail view displays all media fields."""
    media = media_factory(
        title="Complete Media",
        status="COMPLETED",
        score=8,
        review="This is a detailed review.",
        pub_year=2023,
        external_uri="https://example.com",
        contributors=[agent],
    )

    content = logged_in_client.get(reverse("media_detail", kwargs={"pk": media.pk})).content.decode()

    assert media.title in content
    assert "2023" in content
    assert agent.name in content
    assert "https://example.com" in content


def test_media_detail_contributor_links_to_filtered_list(logged_in_client, media, agent):
    """Contributor links of the detail view lead to the list filtered on that contributor, as plain links."""
    content = logged_in_client.get(reverse("media_detail", kwargs={"pk": media.pk})).content.decode()

    link = re.search(r"<a [^>]*contributor-link[^>]*>", content).group(0)
    assert f"contributor={agent.id}" in link
    assert "hx-" not in link


@pytest.mark.parametrize(("fields", "invited"), [({}, True), ({"score": 7, "review": "Fine."}, False)])
def test_media_detail_invites_to_rate_and_review(logged_in_client, media_factory, fields, invited):
    """A media page without score nor review links to the edit form at the field to fill, and only then."""
    media = media_factory(**fields)
    edit = reverse("media_edit", args=[media.pk])

    content = logged_in_client.get(reverse("media_detail", args=[media.pk])).content.decode()

    assert (f'href="{edit}#score-field"' in content) is invited
    assert (f'href="{edit}#review-field"' in content) is invited


def test_media_detail_names_its_external_link_by_domain(logged_in_client, media_factory):
    """The external link of a media page shows the domain it leads to."""
    media = media_factory(external_uri="https://www.themoviedb.org/movie/438631")

    content = logged_in_client.get(reverse("media_detail", args=[media.pk])).content.decode()

    assert re.search(r'href="https://www.themoviedb.org/movie/438631"[\s\S]*?themoviedb.org\s*</span>', content)


# Navigation


def _back_url(response):
    """Return the target of the back link of a page, or None when it has none."""
    match = re.search(
        r'<a href="([^"]*)"\s+class="btn btn-ghost btn-sm btn-circle shrink-0"', response.content.decode()
    )
    return match and match.group(1)


def test_back_links_lead_to_the_parent_page(logged_in_client, media):
    """Back links go up the hierarchy: detail to list, import to edit or list."""
    home = reverse("home")
    detail = reverse("media_detail", args=[media.pk])
    edit = reverse("media_edit", args=[media.pk])

    assert _back_url(logged_in_client.get(detail)) == home
    assert _back_url(logged_in_client.get(reverse("media_import"), {"media_id": media.pk})) == edit
    assert _back_url(logged_in_client.get(reverse("media_import"))) == home


@pytest.mark.parametrize("url_name", ["media_edit", "media_add"])
def test_forms_leave_through_cancel_rather_than_a_back_link(logged_in_client, media, url_name):
    """The edit and add forms have no back link, which would double their Cancel button."""
    args = [media.pk] if url_name == "media_edit" else []

    assert _back_url(logged_in_client.get(reverse(url_name, args=args))) is None


@pytest.mark.parametrize("url_name", ["stats", "backup_manage", "accounts:profile_edit"])
def test_top_level_pages_have_no_back_link(logged_in_client, url_name):
    """Pages reached from the sidebar have no back link."""
    assert _back_url(logged_in_client.get(reverse(url_name))) is None


def test_add_media_is_reachable_from_every_page(logged_in_client, media):
    """The add action is in the sidebar, and in a floating button on pages other than the forms."""
    add_url = reverse("media_import")
    detail = logged_in_client.get(reverse("media_detail", args=[media.pk])).content.decode()
    edit = logged_in_client.get(reverse("media_edit", args=[media.pk])).content.decode()

    assert detail.count(f'href="{add_url}"') == 2
    assert 'class="fab' in detail
    assert 'class="fab' not in edit


def test_sidebar_marks_the_current_saved_view(logged_in_client, saved_view_factory):
    """The saved view matching the current list is highlighted in the sidebar."""
    view = saved_view_factory(name="Games and books", filter_types=["GAME", "BOOK"])
    saved_view_factory(name="Books", filter_types=["BOOK"])

    content = logged_in_client.get(view.get_filter_url()).content.decode()

    assert re.search(rf'<a href="{re.escape(escape(view.get_filter_url()))}"\s+class="[^"]*menu-active', content)
    assert content.count("menu-active") == 1


def test_sidebar_marks_the_current_media_type(logged_in_client):
    """Each media type has its shortcut in the sidebar, highlighted when the list is filtered on it alone."""
    content = logged_in_client.get(reverse("home"), {"type": "FILM"}).content.decode()

    shortcuts = re.findall(r'<a href="/\?type=(\w+)"\s+class="([^"]*)"', content)
    assert shortcuts == [(value, "menu-active" if value == "FILM" else "") for value in MediaType.values]


DISPLAY_UTILITIES = {"block", "inline-block", "inline", "flex", "inline-flex", "grid", "inline-grid", "contents"}


@pytest.mark.parametrize("url_name", ["home", "media_add", "stats"])
def test_closed_dropdown_menus_leave_the_page(logged_in_client, url_name):
    """A dropdown menu sets no display, which would keep it on the page while closed, invisible but clickable."""
    content = logged_in_client.get(reverse(url_name)).content.decode()

    menus = [classes.split() for classes in re.findall(r'class="(dropdown-content[^"]*)"', content)]
    assert menus
    assert [classes for classes in menus if DISPLAY_UTILITIES & set(classes)] == []


@freeze_time("2026-09-25")
def test_sidebar_stats_link_opens_the_current_year(logged_in_client):
    """The statistics shortcut of the sidebar shows the current year."""
    content = logged_in_client.get(reverse("home")).content.decode()

    assert f'<a href="{reverse("stats")}?year=2026"' in content


# Backup


def test_backup_export_creates_and_downloads_backup(logged_in_client, media, monkeypatch, tmp_path):
    """The backup export view creates and returns a backup file."""
    # Write the backup to a temporary directory instead of the project's backups folder
    monkeypatch.setattr("core.views.create_backup", lambda: create_backup(output_dir=tmp_path))

    response = logged_in_client.get(reverse("backup_export"))

    assert len(list(tmp_path.glob("datakult_backup_*.tar.gz"))) == 1
    # Django's FileResponse detects .tar.gz as gzip
    assert response["Content-Type"] == "application/gzip"
    assert "attachment" in response["Content-Disposition"]
    assert "datakult_backup_" in response["Content-Disposition"]


def test_backup_export_failure_is_reported_once(logged_in_client, monkeypatch):
    """A failed export goes back to the backup page, where its error is shown only once, as a toast."""

    def failing_backup():
        msg = "Disk full"
        raise OSError(msg)

    monkeypatch.setattr("core.views.create_backup", failing_backup)

    response = logged_in_client.get(reverse("backup_export"), follow=True)

    assert response.redirect_chain == [(reverse("backup_manage"), 302)]
    assert response.content.decode().count("Disk full") == 1


def test_backup_import_get_redirects(logged_in_client):
    """GET requests to backup import redirect to backup manage."""
    response = logged_in_client.get(reverse("backup_import"))

    assert response.url == reverse("backup_manage")


@pytest.mark.parametrize(
    "upload",
    [None, ("backup.txt", b"not a backup"), ("backup.tar.gz", b"invalid content")],
    ids=["no file", "not an archive", "invalid archive"],
)
def test_backup_import_rejects_what_is_not_a_backup(logged_in_client, upload):
    """Importing no file, or a file that is not a valid backup, goes back to the backup page with an error."""
    data = {"backup_file": SimpleUploadedFile(*upload)} if upload else {}

    response = logged_in_client.post(reverse("backup_import"), data)

    assert response.url == reverse("backup_manage")
    assert messages_of(response)


def test_backup_import_restores_data(logged_in_client, media_factory, tmp_path):
    """The backup import view successfully restores data from a backup."""
    media_factory(title="Original Media", status="COMPLETED")
    backup_path = create_backup(output_dir=tmp_path)
    Media.objects.all().delete()

    uploaded_file = SimpleUploadedFile(backup_path.name, backup_path.read_bytes(), content_type="application/x-tar")
    response = logged_in_client.post(reverse("backup_import"), {"backup_file": uploaded_file})

    assert response.url == reverse("home")
    assert list(Media.objects.values_list("title", "status")) == [("Original Media", "COMPLETED")]


def test_backup_page_has_no_inline_script(logged_in_client):
    """The backup page exports through a plain link, and leaves the import check to a static script."""
    content = logged_in_client.get(reverse("backup_manage")).content.decode()
    body = content.split("</head>")[1]

    assert re.search(rf'<a href="{reverse("backup_export")}"', body)
    assert "js/backup_manage.js" in body
    assert "<script>" not in body
    assert not re.search(r"\sonclick=", body)


# Saved views


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


# Statistics


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

    response = logged_in_client.get(reverse("stats_covers_htmx"), {"year": "2024", "type": "FILM", "page": "2"})

    assert "partials/stats/covers_page.html" in [t.name for t in response.templates]
    covers = response.context["covers"]
    assert covers.number == 2
    assert covers.paginator.count == STATS_COVERS_PER_PAGE + 1
    assert len(covers) == 1


def test_stats_covers_htmx_out_of_range_page_is_empty(logged_in_client, media_factory):
    """A page past the last one adds nothing, instead of repeating the covers already shown."""
    media_factory(score=5)

    response = logged_in_client.get(reverse("stats_covers_htmx"), {"page": "2"})

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


# Import


def test_import_page_title_depends_on_its_purpose(logged_in_client, media):
    """The import page is titled as adding a media, or as importing metadata into an existing one."""
    adding = logged_in_client.get(reverse("media_import")).content.decode()
    importing = logged_in_client.get(reverse("media_import"), {"media_id": media.pk}).content.decode()

    assert "Add media</h1>" in adding
    assert "Import metadata</h1>" in importing


def test_import_page_has_one_search_for_every_source(logged_in_client, media_factory):
    """The import page has a single search field, and picks the source of the media type."""
    media = media_factory(media_type="GAME", title="Hades")

    content = logged_in_client.get(
        reverse("media_import"), {"media_id": media.pk, "media_type": "GAME", "title": "Hades"}
    ).content.decode()

    assert content.count('name="q"') == 1
    assert re.search(r'name="q"[^>]*value="Hades"', content)
    assert content.count('name="source"') == 4
    assert re.search(r'name="source"\s+value="igdb"[^>]*\schecked', content)


@pytest.mark.parametrize("source", ["tmdb", "igdb", "books", "musicbrainz"])
def test_import_search_uses_the_picked_source(logged_in_client, monkeypatch, source):
    """The single search of the import page searches the source picked in its tabs."""
    monkeypatch.setitem(IMPORT_SEARCHES, source, lambda _request: HttpResponse(f"searched {source}"))

    response = logged_in_client.get(reverse("import_search_htmx"), {"source": source, "q": "dune"})

    assert response.content.decode() == f"searched {source}"


@pytest.mark.parametrize("params", [{"q": "dune"}, {"source": "unknown", "q": "dune"}])
def test_import_search_rejects_an_unknown_source(logged_in_client, params):
    """A search without a known source is a bad request."""
    assert logged_in_client.get(reverse("import_search_htmx"), params).status_code == 400


@pytest.mark.parametrize("query", ["", "a"])
@pytest.mark.parametrize("source", ["tmdb", "igdb", "books", "musicbrainz"])
def test_import_search_waits_for_a_longer_query(logged_in_client, source, query):
    """A query shorter than two characters searches nothing, whatever the source, and keeps the edited media."""
    response = logged_in_client.get(reverse("import_search_htmx"), {"source": source, "q": query, "media_id": "42"})

    assert "partials/import/import_results.html" in [t.name for t in response.templates]
    assert response.context["results"] == []
    assert response.context["media_id"] == "42"


IMPORTS = {
    "tmdb movie": (
        {"tmdb_id": "438631", "media_type": "movie", "lang": "fr-FR"},
        {
            "https://api.themoviedb.org/3/movie/438631": {
                "title": "Dune",
                "original_title": "Dune",
                "release_date": "2021-09-15",
                "credits": {
                    "crew": [{"name": "Denis Villeneuve", "job": "Director"}, {"name": "Eric", "job": "Writer"}]
                },
                "production_companies": [{"name": "Legendary"}, {"name": "Warner"}, {"name": "Villeneuve Films"}],
                "genres": [{"name": "Science Fiction"}],
                "poster_path": "/dune.jpg",
            }
        },
        {
            "initial": {
                "title": "Dune",
                "pub_year": 2021,
                "media_type": "FILM",
                "external_uri": "https://www.themoviedb.org/movie/438631",
            },
            "import_contributors": ["Denis Villeneuve", "Legendary", "Warner"],
            "import_tags": ["Science Fiction"],
            "cover_url": "https://image.tmdb.org/t/p/w500/dune.jpg",
        },
    ),
    "tmdb tv": (
        {"tmdb_id": "95396", "media_type": "tv"},
        {
            "https://api.themoviedb.org/3/tv/95396": {
                "name": "Severance",
                "first_air_date": "2022-02-18",
                "created_by": [{"name": "Dan Erickson"}],
                "genres": [{"name": "Drama"}],
            }
        },
        {
            "initial": {
                "title": "Severance",
                "pub_year": 2022,
                "media_type": "TV",
                "external_uri": "https://www.themoviedb.org/tv/95396",
            },
            "import_contributors": ["Dan Erickson"],
            "import_tags": ["Drama"],
            "cover_url": None,
        },
    ),
    "igdb": (
        {"igdb_id": "1"},
        {
            "https://id.twitch.tv/oauth2/token": {"access_token": "token", "expires_in": 3600},
            "https://api.igdb.com/v4/games": [
                {
                    "name": "Hades",
                    "first_release_date": 1600387200,
                    "url": "https://www.igdb.com/games/hades",
                    "cover": {"image_id": "co1"},
                    "involved_companies": [
                        {"company": {"name": "Supergiant"}, "developer": True, "publisher": True},
                        {"company": {"name": "Publisher"}, "developer": False, "publisher": True},
                    ],
                    "genres": [{"name": "Roguelike"}],
                }
            ],
        },
        {
            "initial": {
                "title": "Hades",
                "pub_year": 2020,
                "media_type": "GAME",
                "external_uri": "https://www.igdb.com/games/hades",
            },
            "import_contributors": ["Supergiant"],
            "import_tags": ["Roguelike"],
            "cover_url": "https://images.igdb.com/igdb/image/upload/t_cover_big/co1.jpg",
        },
    ),
    "google books": (
        {"googlebooks_id": "vol1"},
        {
            "https://www.googleapis.com/books/v1/volumes/vol1": {
                "volumeInfo": {
                    "title": "Dune",
                    "subtitle": "Deluxe Edition",
                    "authors": ["Frank Herbert"],
                    "publishedDate": "1965-08",
                    "categories": ["Fiction"],
                    "imageLinks": {"thumbnail": "http://books.google.com/books/content?id=vol1&zoom=1"},
                    "canonicalVolumeLink": "https://books.google.com/books/about/Dune.html",
                }
            }
        },
        {
            "initial": {
                "title": "Dune: Deluxe Edition",
                "pub_year": 1965,
                "media_type": "BOOK",
                "external_uri": "https://books.google.com/books/about/Dune.html",
            },
            "import_contributors": ["Frank Herbert"],
            "import_tags": ["Fiction"],
            "cover_url": "https://books.google.com/books/content?id=vol1&fife=w800-h1200",
        },
    ),
    "openlibrary": (
        {"openlibrary_key": "OL1W", "year": "1965"},
        {
            "https://openlibrary.org/works/OL1W.json": {
                "title": "Dune",
                "covers": [42],
                "authors": [{"author": {"key": "/authors/OL2A"}}],
            },
            "https://openlibrary.org/authors/OL2A.json": {"name": "Frank Herbert"},
        },
        {
            "initial": {
                "title": "Dune",
                "pub_year": 1965,
                "media_type": "BOOK",
                "external_uri": "https://openlibrary.org/works/OL1W",
            },
            "import_contributors": ["Frank Herbert"],
            "import_tags": [],
            "cover_url": "https://covers.openlibrary.org/b/id/42-L.jpg",
        },
    ),
    "musicbrainz": (
        {"musicbrainz_id": "abc-123"},
        {
            "https://musicbrainz.org/ws/2/release/abc-123": {
                "title": "Abbey Road",
                "date": "1969-09-26",
                "artist-credit": [{"name": "The Beatles"}],
                "genres": [{"name": "rock"}],
                "tags": [{"name": "rock"}, {"name": "pop"}],
            }
        },
        {
            "initial": {
                "title": "Abbey Road",
                "pub_year": 1969,
                "media_type": "MUSIC",
                "external_uri": "https://musicbrainz.org/release/abc-123",
            },
            "import_contributors": ["The Beatles"],
            "import_tags": ["rock", "pop"],
            "cover_url": "https://coverartarchive.org/release/abc-123/front-500",
        },
    ),
}


@pytest.mark.parametrize(("params", "responses", "expected"), IMPORTS.values(), ids=IMPORTS.keys())
def test_import_fills_the_form_with_the_metadata_of_the_source(
    logged_in_client, api_responses, params, responses, expected
):
    """Importing from a source fills the form, and suggests its contributors, tags and cover."""
    api_responses.update(responses)

    response = logged_in_client.get(reverse("media_add"), params)

    assert response.context["form"].initial == expected["initial"]
    assert response.context["import_contributors"] == expected["import_contributors"]
    assert response.context["import_tags"] == expected["import_tags"]
    assert response.context["import_data"]["cover_url"] == expected["cover_url"]


def test_import_into_a_media_keeps_its_review_and_contributors(logged_in_client, api_responses, media):
    """Importing into a media keeps what was reviewed, and only suggests the contributors it does not have yet."""
    params, responses, _expected = IMPORTS["tmdb tv"]
    api_responses.update(responses)
    api_responses["https://api.themoviedb.org/3/tv/95396"]["created_by"].append({"name": "test author"})
    media.status, media.score, media.review = "COMPLETED", 8, "Unsettling."
    media.save()

    response = logged_in_client.get(reverse("media_edit", args=[media.pk]), params)

    initial = response.context["form"].initial
    assert (initial["title"], initial["status"], initial["score"], initial["review"]) == (
        "Severance",
        "COMPLETED",
        8,
        "Unsettling.",
    )
    assert response.context["import_contributors"] == ["Dan Erickson"]


def test_import_that_fails_shows_an_empty_form(logged_in_client, api_responses):
    """When the source cannot be reached, the form is shown empty rather than failing."""
    response = logged_in_client.get(reverse("media_add"), {"musicbrainz_id": "unknown"})

    assert response.context["import_data"] is None
    assert not response.context["form"].initial


SEARCHES = {
    "tmdb": {
        "https://api.themoviedb.org/3/search/multi": {
            "results": [
                {
                    "media_type": "movie",
                    "id": 1,
                    "title": "Dune",
                    "original_title": "Dune",
                    "release_date": "2021-09-15",
                },
                {"media_type": "tv", "id": 2, "name": "Dune: Prophecy", "first_air_date": "2024-11-17"},
                {"media_type": "person", "id": 3, "name": "Frank Herbert"},
            ]
        }
    },
    "igdb": {
        "https://id.twitch.tv/oauth2/token": {"access_token": "token", "expires_in": 3600},
        "https://api.igdb.com/v4/games": [{"id": 1, "name": "Dune: Spice Wars", "first_release_date": 1650931200}],
    },
    "books": {
        "https://openlibrary.org/search.json": {
            "docs": [
                {"key": "/works/OL1W", "title": "Dune", "author_name": "Frank Herbert", "first_publish_year": 1965}
            ]
        },
        "https://www.googleapis.com/books/v1/volumes": {
            "items": [
                {
                    "id": "v1",
                    "volumeInfo": {"title": "Dune Messiah", "authors": ["Frank Herbert"], "publishedDate": "1969"},
                }
            ]
        },
    },
    "musicbrainz": {
        "https://musicbrainz.org/ws/2/release": {
            "releases": [
                {"id": "m1", "title": "Dune (OST)", "date": "2021-09-03", "artist-credit": [{"name": "Hans Zimmer"}]}
            ]
        }
    },
}


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("tmdb", [("Dune", 2021, ""), ("Dune: Prophecy", 2024, "")]),
        ("igdb", [("Dune: Spice Wars", 2022, "")]),
        ("books", [("Dune Messiah", 1969, "Frank Herbert"), ("Dune", 1965, "Frank Herbert")]),
        ("musicbrainz", [("Dune (OST)", 2021, "Hans Zimmer")]),
    ],
)
def test_import_search_shows_the_results_of_the_source(logged_in_client, api_responses, source, expected):
    """A search shows the works found by the source, with their year and authors, leaving out anything else."""
    api_responses.update(SEARCHES[source])

    response = logged_in_client.get(reverse("import_search_htmx"), {"source": source, "q": "dune"})

    assert [(result.title, result.year, result.byline) for result in response.context["results"]] == expected


@pytest.mark.parametrize(
    "responses", [{}, {"https://id.twitch.tv/oauth2/token": {"expires_in": 3600}}], ids=["unreachable", "no token"]
)
def test_import_search_without_a_twitch_token_fails_gracefully(logged_in_client, api_responses, responses):
    """When Twitch gives no token for IGDB, the game search says it failed, rather than breaking the page."""
    api_responses.update(responses)

    response = logged_in_client.get(reverse("import_search_htmx"), {"source": "igdb", "q": "dune"})

    assert response.context["error"] == "Search failed"


def test_import_search_failure_is_logged_once(logged_in_client, api_responses, caplog):
    """A source that cannot be reached is logged once, by its client, rather than by every layer it goes through."""
    response = logged_in_client.get(reverse("import_search_htmx"), {"source": "musicbrainz", "q": "dune"})

    assert response.context["error"] == "Search failed"
    assert [record.levelname for record in caplog.records if record.levelno >= logging.WARNING] == ["WARNING"]
