"""
Tests for core.views.media: the media list, a media, its form, and the contributors and tags picked in it.
"""

import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string
from django.urls import reverse
from freezegun import freeze_time
from PIL import Image

from core.models import Agent, Media, Tag
from tests.helpers import image_bytes, media_form_data, messages_of, titles


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
    monkeypatch.setattr("core.views.imports._download_cover", lambda _url: cover_png)
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
        monkeypatch.setattr("core.views.imports._download_cover", lambda _url: tiff)
        data["import_cover_url"] = "https://image.tmdb.org/t/p/w500/cover.jpg"
    else:
        data["cover"] = SimpleUploadedFile("cover.tiff", tiff)

    response = logged_in_client.post(reverse("media_edit", kwargs={"pk": media.pk}), data)

    assert response.context["form"].has_error("cover")
    media.refresh_from_db()
    assert not media.cover


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            {"field_name": "title", "title": ""},
            '<span class="label-text-alt text-error">This field is required.</span>',
        ),
        ({"field_name": "title", "title": "Valid Title"}, ""),
        *[({"field_name": field_name}, "") for field_name in ["cover", "contributors", "review", "score"]],
        ({"field_name": "unknown"}, ""),
    ],
)
def test_validate_media_field_returns_the_error_of_that_field(logged_in_client, data, expected):
    """A field is validated alone: its error if it has one, nothing for optional fields left empty or unknown fields."""
    response = logged_in_client.post(reverse("media_validate_field"), data)

    assert response.content.decode().strip() == expected


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


@pytest.mark.parametrize(
    ("model", "search", "select", "chips_id"),
    [
        (Agent, "agent_search_htmx", "agent_select_htmx", "contributors-chips"),
        (Tag, "tag_search_htmx", "tag_select_htmx", "tags-chips"),
    ],
)
def test_suggestions_add_the_picked_object_to_its_chips(logged_in_client, model, search, select, chips_id):
    """A suggested contributor or tag, once picked, is added to the chips of its field."""
    model.objects.create(name="Frank Herbert")

    content = logged_in_client.get(reverse(search), {"q": "Frank"}).content.decode()

    assert "Frank Herbert</a>" in content
    assert f'hx-post="{reverse(select)}"' in content
    assert f'hx-target="#{chips_id}"' in content


def test_agent_select_returns_chip(logged_in_client, agent):
    """Selecting an agent returns the chip template."""
    response = logged_in_client.post(reverse("agent_select_htmx"), {"id": agent.pk})

    assert response.context["agent"] == agent


def test_agent_select_nonexistent(logged_in_client, db):
    """Selecting a non-existent agent returns error."""
    response = logged_in_client.post(reverse("agent_select_htmx"), {"id": 99999})

    assert response.context["error"] == "Agent not found"


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
