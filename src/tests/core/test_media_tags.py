"""
Tests for core.templatetags.media_tags module.

These tests verify the custom template tags and filters used by the media templates.
"""

import re

import pytest
from django.template.loader import render_to_string
from django.utils import translation
from partial_date import PartialDate

from core.models import Agent
from core.templatetags.media_tags import has_filters, is_current_url, partial_date, score_color, status_icon


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", False),
        ("?sort=-score", False),
        ("?tag=", False),
        ("?tag=3", True),
        ("?contributor=1", True),
        ("?status=PLANNED", True),
    ],
)
def test_has_filters(rf, query, expected):
    """has_filters is true only when a filter parameter has a value."""
    assert has_filters(rf.get(f"/{query}")) is expected


@pytest.mark.parametrize(
    ("value", "language", "expected"),
    [
        ("2024-05-12", "en", "May 12, 2024"),
        ("2024-05-12", "fr", "12 mai 2024"),
        ("2024-05", "en", "May 2024"),
        ("2024-05", "fr", "mai 2024"),
        ("2024", "fr", "2024"),
    ],
)
def test_partial_date_is_localized_to_its_precision(value, language, expected):
    """A partial date is displayed in the active language, down to its own precision only."""
    with translation.override(language):
        assert partial_date(PartialDate(value)) == expected


def test_partial_date_without_value_is_empty():
    """A missing date renders as an empty string."""
    assert partial_date(None) == ""


def test_score_ring_shows_score_and_verdict():
    """The score ring fills in proportion to the score and names its verdict."""
    html = render_to_string("partials/media_items/score/media_score_ring.html", {"score": 8, "label": "Loved it"})

    assert "--value:80" in html
    assert 'aria-valuenow="8"' in html
    assert "Loved it" in html


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (1, "text-red-500"),
        (4, "text-red-500"),
        (5, "text-amber-500"),
        (6, "text-lime-500"),
        (7, "text-green-500"),
        (8, "text-green-500"),
        (9, "text-emerald-600"),
        (10, "text-emerald-600"),
    ],
)
def test_score_color_follows_the_verdict(score, expected):
    """Scores are coloured by verdict, from red for disliked media to green as soon as they are appreciated."""
    assert score_color(score) == expected


def test_score_ring_is_coloured_by_score():
    """The score arc takes the colour of its verdict."""
    html = render_to_string("partials/media_items/score/media_score_ring.html", {"score": 9})

    assert "text-emerald-600" in html


def test_score_ring_without_score_renders_nothing():
    """No ring is rendered for an unrated media."""
    html = render_to_string("partials/media_items/score/media_score_ring.html", {"score": None})

    assert not html.strip()


def test_page_header_links_back_when_given_a_url():
    """The page header shows its title, and a back link only when a back URL is given."""
    with_back = render_to_string("partials/common/page_header.html", {"title": "Dune", "back_url": "/media/1/"})
    without_back = render_to_string("partials/common/page_header.html", {"title": "Dune"})

    assert "Dune</h1>" in with_back
    assert 'href="/media/1/"' in with_back
    assert "href=" not in without_back


def test_filter_badge_shows_its_dimension_icon():
    """A filter badge can carry the icon of the dimension it filters on, before its remove button."""
    with_icon = render_to_string("partials/filters/filter_badge.html", {"label": "Dune", "icon": "tag"})
    without_icon = render_to_string("partials/filters/filter_badge.html", {"label": "Dune"})

    assert with_icon.count("<svg") == without_icon.count("<svg") + 1


@pytest.mark.parametrize(
    ("current", "url", "expected"),
    [
        ("/?status=PLANNED&sort=-score", "/?sort=-score&status=PLANNED", True),
        ("/?status=PLANNED&sort=-score&page=2", "/?sort=-score&status=PLANNED", True),
        ("/?status=PLANNED&tag=", "/?status=PLANNED", True),
        ("/?status=PLANNED", "/?status=PLANNED&status=DNF", False),
        ("/stats/?status=PLANNED", "/?status=PLANNED", False),
    ],
)
def test_is_current_url(rf, current, url, expected):
    """A URL is current when it has the same path and non-empty parameters, in any order, whatever the page."""
    assert is_current_url(rf.get(current), url) is expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("PLANNED", "clock"),
        ("IN_PROGRESS", "play"),
        ("PAUSED", "pause"),
        ("COMPLETED", "circle-check"),
        ("DNF", "circle-x"),
    ],
)
def test_status_icon_matches_the_sidebar(status, expected):
    """Each status is shown with the icon of its entry in the sidebar."""
    assert status_icon(status) == expected


def test_contributors_are_separated_by_commas(rf, media_factory, agent):
    """Contributors are listed with commas, with no space before them."""
    media = media_factory()
    media.contributors.add(agent, Agent.objects.create(name="Second Author"))

    html = render_to_string("partials/media_items/media_contributors.html", {"media": media, "request": rf.get("/")})

    assert re.search(r"</a>,\s+<a", html)
