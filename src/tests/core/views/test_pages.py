"""
Tests of what every page shares: its access, its navigation and its sidebar.
"""

import re
from html import unescape

import pytest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import escape
from freezegun import freeze_time

from accounts import urls as accounts_urls
from core import urls as core_urls
from core.models import MediaType


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


@pytest.mark.parametrize(("url_name", "title"), [("home", "My media"), ("stats", "Statistics"), ("login", "Log in")])
def test_page_titles_end_with_the_name_of_the_app(logged_in_client, url_name, title):
    """The title of a page names the page, then the app."""
    content = logged_in_client.get(reverse(url_name)).content.decode()

    assert " ".join(re.search(r"<title>(.*?)</title>", content, re.DOTALL)[1].split()) == f"{title} | Datakult"


@pytest.mark.parametrize("url_name", ["home", "login"])
def test_shared_script_is_left_out_of_the_body(logged_in_client, url_name):
    """The script of every page is loaded once, in the head, as htmx runs again the scripts of a body it swaps."""
    head, body = logged_in_client.get(reverse(url_name)).content.decode().split("</head>")

    assert re.search(r'<script src="[^"]*js/base\.js" defer></script>', head)
    assert "js/base.js" not in body


def test_pages_declare_the_active_language(logged_in_client):
    """The html lang attribute follows the language of the request."""
    response = logged_in_client.get(reverse("home"), HTTP_ACCEPT_LANGUAGE="fr")

    assert '<html lang="fr">' in response.content.decode()


def _back_url(response):
    """Return the target of the back link of a page, or None when it has none."""
    match = re.search(
        r'<a href="([^"]*)"\s+class="btn btn-ghost btn-sm btn-circle shrink-0"', response.content.decode()
    )
    return match and match[1]


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


def test_sidebar_marks_the_current_status(logged_in_client):
    """Each status has its shortcut in the sidebar, the one of completed media showing the unfinished ones too."""
    content = logged_in_client.get(reverse("home"), {"status": ["COMPLETED", "DNF"]}).content.decode()

    shortcuts = re.findall(r'<a href="/\?(status=[^"]+)"\s+class="([^"]*)"', content)
    assert [(unescape(query), classes) for query, classes in shortcuts] == [
        ("status=PLANNED", ""),
        ("status=IN_PROGRESS", ""),
        ("status=PAUSED", ""),
        ("status=COMPLETED&status=DNF", "menu-active"),
    ]


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
    assert not [classes for classes in menus if DISPLAY_UTILITIES & set(classes)]


@freeze_time("2026-09-25")
def test_sidebar_stats_link_opens_the_current_year(logged_in_client):
    """The statistics shortcut of the sidebar shows the current year."""
    content = logged_in_client.get(reverse("home")).content.decode()

    assert f'<a href="{reverse("stats")}?year=2026"' in content


@pytest.mark.parametrize(
    ("url", "modal_id"),
    [
        (lambda media: reverse("media_edit", args=[media.pk]), "confirm-delete-modal"),
        (lambda media: reverse("home") + "?type=BOOK", "save-view-modal"),
    ],
    ids=["delete media", "save view"],
)
def test_modals_are_dialogs_opened_by_their_button(logged_in_client, media, url, modal_id):
    """A modal is a dialog, which a button of the page opens."""
    content = logged_in_client.get(url(media)).content.decode()

    assert re.search(rf'<dialog id="{modal_id}"\s+class="modal"', content)
    assert re.search(rf'<button type="button"\s+commandfor="{modal_id}"\s+command="show-modal"', content)


def test_confirm_modal_submits_the_form_it_confirms():
    """The confirmation dialog submits the form it confirms, and closes by its cancel button or its backdrop."""
    html = render_to_string(
        "partials/common/confirm_modal.html", {"modal_id": "confirm", "form_id": "delete", "title": "", "message": ""}
    )

    assert re.search(r'<button type="submit"\s+form="delete"', html)
    assert len(re.findall(r'commandfor="confirm"\s+command="close"', html)) == 2
    assert "<form" not in html


@pytest.mark.parametrize(
    ("url_name", "triggers"),
    [
        ("home", {"input changed delay:300ms from:#search-input"}),
        ("media_import", {"input changed delay:300ms from:#import-query"}),
        ("media_add", {"input changed delay:300ms", "input changed delay:500ms"}),
        ("accounts:profile_edit", {"input changed delay:500ms"}),
    ],
)
def test_typing_triggers_requests_once_it_pauses(logged_in_client, url_name, triggers):
    """Typed or pasted text is searched 300 ms after typing pauses, and a field is validated 500 ms after."""
    content = logged_in_client.get(reverse(url_name)).content.decode()

    typing = {
        event.strip()
        for trigger in re.findall(r'hx-trigger="([^"]*)"', content)
        for event in trigger.split(",")
        if event.strip().startswith(("input", "keyup", "keydown"))
    }
    assert typing == triggers
