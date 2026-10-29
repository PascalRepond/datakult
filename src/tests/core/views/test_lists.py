"""
Tests for core.views.lists: the lists in which each user ranks media.
"""

import re
from datetime import UTC, datetime

import pytest
from django.urls import reverse
from freezegun import freeze_time

from core.models import CustomList, ListEntry, Media
from core.views.lists import LISTS_PER_PAGE
from tests.helpers import messages_of

# Date set as the last update of a list, to see whether a change marks it updated
LONG_AGO = datetime(2020, 1, 1, tzinfo=UTC)


@pytest.fixture
def ranked_media(custom_list, media_factory):
    """Fill the list with three media, ranked in the order of their titles."""
    ranked = [media_factory(title=title) for title in ("First", "Second", "Third")]
    for position, media in enumerate(ranked, start=1):
        custom_list.media.add(media, through_defaults={"position": position})
    return ranked


def _ranked_titles(custom_list):
    """Return the titles of the media of a list, in their order."""
    return [entry.media.title for entry in custom_list.entries.all()]


def test_list_index_shows_only_the_lists_of_the_user(logged_in_client, user, other_user):
    """The lists page links to the lists of the user, with their description, and not to those of other users."""
    own = CustomList.objects.create(user=user, name="Top films", description="The best of the year")
    CustomList.objects.create(user=other_user, name="Other list")

    response = logged_in_client.get(reverse("list_index"))

    assert list(response.context["page_obj"]) == [own]
    assert f'href="{reverse("list_detail", args=[own.pk])}"' in response.content.decode()
    assert "The best of the year" in response.content.decode()


def _list_names(response):
    """Return the names of the lists shown by a response, in their order."""
    return [custom_list.name for custom_list in response.context["page_obj"]]


@pytest.mark.parametrize(
    ("search", "names"),
    [("best", ["Top films"]), ("GAM", ["Games"]), ("nothing", [])],
    ids=["description", "name", "none"],
)
def test_list_index_searches_the_names_and_descriptions(logged_in_client, user, search, names):
    """The search keeps the lists whose name or description holds it, whatever its case, or says that none does."""
    CustomList.objects.create(user=user, name="Top films", description="The best of the year")
    CustomList.objects.create(user=user, name="Games")

    response = logged_in_client.get(reverse("list_index"), {"search": search})

    assert _list_names(response) == names
    assert ("No list matches this search." in response.content.decode()) is (names == [])


@pytest.mark.parametrize(
    ("sort", "names"),
    [("-updated_at", ["Zelda", "alpha"]), ("name", ["alpha", "Zelda"]), ("invalid", ["Zelda", "alpha"])],
    ids=["updated", "name", "invalid"],
)
def test_list_index_sorts_by_update_or_name(logged_in_client, user, sort, names):
    """The lists come last updated first, or by name whatever its case, the default for an unknown sort."""
    with freeze_time("2026-01-01"):
        CustomList.objects.create(user=user, name="alpha")
    with freeze_time("2026-02-01"):
        CustomList.objects.create(user=user, name="Zelda")

    assert _list_names(logged_in_client.get(reverse("list_index"), {"sort": sort})) == names


@pytest.mark.parametrize("sort", ["-updated_at", "name"])
def test_list_index_shows_tied_lists_newest_first(logged_in_client, user, sort):
    """Lists that tie on the sort come newest first, for their order to hold from one page to the next."""
    with freeze_time("2026-01-01"):
        tied = [CustomList.objects.create(user=user, name="Top 10") for _ in range(3)]

    response = logged_in_client.get(reverse("list_index"), {"sort": sort})

    assert list(response.context["page_obj"]) == tied[::-1]


def test_lists_load_page_by_page(logged_in_client, user):
    """The lists page shows a first page of lists, and loads the next ones as it scrolls."""
    CustomList.objects.bulk_create(
        CustomList(user=user, name=f"List {number:02}") for number in range(LISTS_PER_PAGE + 1)
    )

    first_page = logged_in_client.get(reverse("list_index"), {"sort": "name"})
    next_page = logged_in_client.get(reverse("load_more_lists"), {"sort": "name", "page": 2})

    assert len(first_page.context["page_obj"]) == LISTS_PER_PAGE
    assert f"{reverse('load_more_lists')}?sort=name&amp;page=2" in first_page.content.decode()
    assert _list_names(next_page) == [f"List {LISTS_PER_PAGE:02}"]


def test_list_cards_show_the_first_covers_and_the_count(logged_in_client, custom_list, media_factory):
    """The card of a list shows its first four media, and counts them all."""
    for title in ("One", "Two", "Three", "Four", "Five"):
        custom_list.append(media_factory(title=title))

    response = logged_in_client.get(reverse("list_index"))

    card = response.context["page_obj"][0]
    assert [entry.media.title for entry in card.first_entries] == ["One", "Two", "Three", "Four"]
    assert "5 media" in response.content.decode()


def test_list_add_creates_a_list_of_the_user(logged_in_client, user):
    """A list is created for the user, who goes back to the lists page."""
    response = logged_in_client.post(reverse("list_add"), {"name": "Top films", "description": "Of 2026"})

    assert CustomList.objects.filter(user=user, name="Top films", description="Of 2026").exists()
    assert response.url == reverse("list_index")
    assert messages_of(response) == ["List 'Top films' created successfully"]


def test_list_edit_updates_the_list(logged_in_client, custom_list):
    """A list is updated from its page, where the user goes back."""
    response = logged_in_client.post(reverse("list_edit", args=[custom_list.pk]), {"name": "Top series"})

    custom_list.refresh_from_db()
    assert custom_list.name == "Top series"
    assert response.url == reverse("list_detail", args=[custom_list.pk])
    assert messages_of(response) == ["List 'Top series' updated successfully"]


@pytest.mark.parametrize("url_name", ["list_add", "list_edit"])
@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"name": "  "}, "Name: This field is required."),
        ({"name": "Top series", "description": "Of\x002026"}, "Description: Null characters are not allowed."),
    ],
    ids=["blank name", "null character"],
)
def test_list_forms_reject_an_invalid_field(logged_in_client, custom_list, url_name, data, message):
    """A list with an invalid field is neither created nor updated, and the error of the field is shown."""
    args = [custom_list.pk] if url_name == "list_edit" else []

    response = logged_in_client.post(reverse(url_name, args=args), data)

    assert list(CustomList.objects.values_list("name", flat=True)) == ["Top films"]
    assert messages_of(response) == [message]


def test_list_edit_does_not_create_the_list_it_cannot_find(logged_in_client):
    """Updating a list that does not exist, even numbered 0, is not found rather than creating a list."""
    response = logged_in_client.post(reverse("list_edit", args=[0]), {"name": "Zero"})

    assert response.status_code == 404
    assert not CustomList.objects.exists()


@pytest.mark.parametrize(
    ("url_name", "redirect_name"),
    [("list_add", "list_index"), ("list_edit", "list_detail"), ("list_delete", "list_detail")],
)
def test_list_actions_ignore_get_requests(logged_in_client, custom_list, url_name, redirect_name):
    """GET requests to create, update or delete a list change nothing, and lead back to its page or to the lists."""
    args = [] if url_name == "list_add" else [custom_list.pk]
    redirect_args = [] if redirect_name == "list_index" else [custom_list.pk]

    response = logged_in_client.get(reverse(url_name, args=args))

    assert response.url == reverse(redirect_name, args=redirect_args)
    assert list(CustomList.objects.values_list("name", flat=True)) == ["Top films"]


def test_list_detail_shows_the_ranked_media(logged_in_client, custom_list, ranked_media):
    """The list page shows its media in their order, with their year and score."""
    first = ranked_media[0]
    first.pub_year, first.score = 1999, 8
    first.save()

    response = logged_in_client.get(reverse("list_detail", args=[custom_list.pk]))

    content = response.content.decode()
    assert [entry.media.title for entry in response.context["entries"]] == ["First", "Second", "Third"]
    assert "1999" in content
    assert 'aria-label="Score: 8 out of 10"' in content


def test_list_detail_edits_and_deletes_the_list_through_dialogs(logged_in_client, custom_list):
    """The list page edits the list in a dialog filled with it, and confirms its deletion in another."""
    content = logged_in_client.get(reverse("list_detail", args=[custom_list.pk])).content.decode()

    edit_dialog = re.search(r'<dialog id="edit-list-modal".*?</dialog>', content, re.DOTALL)[0]
    assert f'action="{reverse("list_edit", args=[custom_list.pk])}"' in edit_dialog
    assert 'value="Top films"' in edit_dialog
    delete_dialog = re.search(r'<dialog id="delete-list-modal".*?</dialog>', content, re.DOTALL)[0]
    delete_url = reverse("list_delete", args=[custom_list.pk])
    assert re.search(rf'<form id="delete-list-form"\s+method="post"\s+action="{delete_url}"', content)
    assert re.search(r'<button type="submit"\s+form="delete-list-form"', delete_dialog)


def test_list_delete_keeps_its_media(logged_in_client, custom_list, ranked_media):
    """Deleting a list removes it, but not its media, and leads back to the lists page."""
    response = logged_in_client.post(reverse("list_delete", args=[custom_list.pk]))

    assert not CustomList.objects.exists()
    assert Media.objects.count() == len(ranked_media)
    assert response.url == reverse("list_index")
    assert messages_of(response) == ["List 'Top films' deleted successfully"]


def test_list_media_search_leaves_out_the_media_of_the_list(logged_in_client, custom_list, ranked_media, media_factory):
    """The search suggests the media whose title holds the query, except those already in the list."""
    media_factory(title="Firstborn")

    response = logged_in_client.get(reverse("list_media_search", args=[custom_list.pk]), {"q": "first"})

    assert [media.title for media in response.context["found"]] == ["Firstborn"]


@pytest.mark.parametrize(("query", "shown"), [("  ", False), ("nothing", True)], ids=["empty", "unknown"])
def test_list_media_search_says_when_nothing_is_found(logged_in_client, custom_list, query, shown):
    """A search finding nothing says so, while an empty search shows nothing."""
    response = logged_in_client.get(reverse("list_media_search", args=[custom_list.pk]), {"q": query})

    assert ("No results found" in response.content.decode()) is shown


def test_list_entry_add_appends_the_media(logged_in_client, custom_list, ranked_media, media_factory):
    """A media is added at the end of the list, returned with the search emptied for the next one."""
    fourth = media_factory(title="Fourth")

    response = logged_in_client.post(reverse("list_entry_add", args=[custom_list.pk]), {"media": fourth.pk})

    content = response.content.decode()
    assert _ranked_titles(custom_list) == ["First", "Second", "Third", "Fourth"]
    assert '<div id="list-entries">' in content
    assert re.search(r'<div id="list-media-search"\s+class="relative mb-6"\s+hx-swap-oob="true"', content)


def test_list_entry_add_keeps_a_media_once(logged_in_client, custom_list, media):
    """A media added twice keeps the single place it took in the list, which the second time leaves unchanged."""
    url = reverse("list_entry_add", args=[custom_list.pk])
    logged_in_client.post(url, {"media": media.pk})
    CustomList.objects.update(updated_at=LONG_AGO)

    logged_in_client.post(url, {"media": media.pk})

    custom_list.refresh_from_db()
    assert list(custom_list.entries.values_list("media", "position")) == [(media.pk, 1)]
    assert custom_list.updated_at == LONG_AGO


def test_list_entry_remove_takes_the_media_out_of_the_list(logged_in_client, custom_list, ranked_media):
    """A removed media leaves the list but stays in the library, the others keeping their order."""
    entry = custom_list.entries.get(media=ranked_media[1])

    response = logged_in_client.post(reverse("list_entry_remove", args=[entry.pk]))

    assert _ranked_titles(custom_list) == ["First", "Third"]
    assert [entry.media.title for entry in response.context["entries"]] == ["First", "Third"]
    assert Media.objects.filter(pk=ranked_media[1].pk).exists()


@pytest.mark.parametrize(
    ("index", "direction", "titles"),
    [
        (1, "up", ["Second", "First", "Third"]),
        (1, "down", ["First", "Third", "Second"]),
        (0, "up", ["First", "Second", "Third"]),
        (2, "down", ["First", "Second", "Third"]),
    ],
    ids=["up", "down", "first up", "last down"],
)
def test_list_entry_move_swaps_a_media_with_its_neighbour(logged_in_client, ranked_media, index, direction, titles):
    """A media swaps places with the one above or below it, the first and last staying in place at the edges."""
    entry = ListEntry.objects.get(media=ranked_media[index])

    response = logged_in_client.post(reverse("list_entry_move", args=[entry.pk]), {"direction": direction})

    assert _ranked_titles(entry.custom_list) == titles
    assert [entry.media.title for entry in response.context["entries"]] == titles


def test_list_entry_move_skips_the_gaps_between_positions(logged_in_client, custom_list, media_factory):
    """A media swaps places with its neighbour, however far apart their positions are."""
    custom_list.media.add(media_factory(title="First"), through_defaults={"position": 2})
    custom_list.media.add(media_factory(title="Second"), through_defaults={"position": 7})

    logged_in_client.post(reverse("list_entry_move", args=[custom_list.entries.last().pk]), {"direction": "up"})

    assert _ranked_titles(custom_list) == ["Second", "First"]


def test_media_detail_offers_the_lists_of_the_user(logged_in_client, user, other_user, custom_list, media):
    """The media page offers the lists of the user, checked and first when they hold the media, then last updated."""
    custom_list.append(media)
    with freeze_time("2026-01-01"):
        CustomList.objects.create(user=user, name="Old list")
    CustomList.objects.create(user=user, name="Empty list")
    CustomList.objects.create(user=other_user, name="Other list")

    response = logged_in_client.get(reverse("media_detail", args=[media.pk]))

    lists = [(custom_list.name, custom_list.has_media) for custom_list in response.context["lists"]]
    assert lists == [("Top films", True), ("Empty list", False), ("Old list", False)]


@pytest.mark.parametrize(
    ("search", "names"), [("TOP", ["Top series", "Top films"]), ("nothing", [])], ids=["found", "none"]
)
def test_media_lists_search_htmx_finds_the_lists_by_name(logged_in_client, user, media, search, names):
    """The menu of a media page searches the lists of the user by name, whatever its case, or says it finds none."""
    for name in ("Top films", "Top series", "Games"):
        CustomList.objects.create(user=user, name=name)

    response = logged_in_client.get(reverse("media_lists_search_htmx", args=[media.pk]), {"q": search})

    assert [custom_list.name for custom_list in response.context["lists"]] == names
    assert ("No results found" in response.content.decode()) is (names == [])


def test_media_lists_htmx_adds_a_checked_media_at_the_end(logged_in_client, custom_list, ranked_media, media_factory):
    """Checking a list on a media page adds the media at the end of the list."""
    fourth = media_factory(title="Fourth")

    response = logged_in_client.post(
        reverse("media_lists_htmx", args=[fourth.pk]), {"list": custom_list.pk, "checked": "1"}
    )

    assert response.status_code == 204
    assert _ranked_titles(custom_list) == ["First", "Second", "Third", "Fourth"]


def test_media_lists_htmx_takes_an_unchecked_media_out(logged_in_client, custom_list, ranked_media):
    """Unchecking a list on a media page takes the media out of the list."""
    logged_in_client.post(reverse("media_lists_htmx", args=[ranked_media[0].pk]), {"list": custom_list.pk})

    assert _ranked_titles(custom_list) == ["Second", "Third"]


def test_media_lists_boxes_go_back_unless_their_change_is_saved(logged_in_client, custom_list, media):
    """A box of the media page takes back its state when its change is not saved, as htmx then swaps nothing."""
    content = logged_in_client.get(reverse("media_detail", args=[media.pk])).content.decode()

    assert 'hx-on::after-request="if (event.detail.xhr.status !== 204) this.checked = !this.checked"' in content


@pytest.mark.parametrize(
    "post",
    [
        lambda custom_list, media: (reverse("list_entry_add", args=[custom_list.pk]), {"media": "abc"}),
        lambda custom_list, media: (reverse("media_lists_htmx", args=[media.pk]), {"list": "abc", "checked": "1"}),
    ],
    ids=["media", "list"],
)
def test_posted_ids_that_are_not_numbers_are_not_found(logged_in_client, custom_list, media, post):
    """A media or a list posted under an ID that is not a number is not found."""
    url, data = post(custom_list, media)

    assert logged_in_client.post(url, data).status_code == 404


@pytest.mark.parametrize(
    "change",
    [
        lambda custom_list, media: (reverse("list_entry_add", args=[custom_list.pk]), {"media": media.pk}),
        lambda custom_list, media: (reverse("list_entry_remove", args=[custom_list.entries.first().pk]), {}),
        lambda custom_list, media: (
            reverse("list_entry_move", args=[custom_list.entries.first().pk]),
            {"direction": "down"},
        ),
        lambda custom_list, media: (
            reverse("media_lists_htmx", args=[media.pk]),
            {"list": custom_list.pk, "checked": "1"},
        ),
        lambda custom_list, media: (
            reverse("media_lists_htmx", args=[custom_list.entries.first().media.pk]),
            {"list": custom_list.pk},
        ),
    ],
    ids=["add", "remove", "move", "check on media page", "uncheck on media page"],
)
def test_changing_the_media_of_a_list_marks_it_updated(
    logged_in_client, custom_list, ranked_media, media_factory, change
):
    """A list counts as updated once a media is added to it, removed from it or moved in it."""
    url, data = change(custom_list, media_factory(title="New"))
    CustomList.objects.update(updated_at=LONG_AGO)

    logged_in_client.post(url, data)

    custom_list.refresh_from_db()
    assert custom_list.updated_at > LONG_AGO


@pytest.mark.parametrize(
    "url_name",
    [
        "list_detail",
        "list_edit",
        "list_delete",
        "list_media_search",
        "list_entry_add",
        "list_entry_remove",
        "list_entry_move",
        "media_lists_htmx",
    ],
)
def test_lists_of_other_users_are_not_found(logged_in_client, other_user, media_factory, url_name):
    """The lists of other users can be neither seen, updated, deleted, searched, filled, emptied nor reordered."""
    other_list = CustomList.objects.create(user=other_user, name="Other list")
    entry = ListEntry.objects.create(custom_list=other_list, media=media_factory(), position=1)
    pk = {"list_entry_remove": entry.pk, "list_entry_move": entry.pk, "media_lists_htmx": entry.media.pk}.get(
        url_name, other_list.pk
    )
    data = {"name": "Taken", "media": media_factory().pk, "direction": "up", "list": other_list.pk}

    response = logged_in_client.post(reverse(url_name, args=[pk]), data)

    assert response.status_code == 404
    assert CustomList.objects.get().name == "Other list"
    assert list(other_list.entries.all()) == [entry]
