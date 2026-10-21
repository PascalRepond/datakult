"""
Tests for core.views.home: the home page, rows of the media in progress, recently rated, planned or without review.
"""

import re

import pytest
from django.urls import reverse
from django.utils.html import escape
from freezegun import freeze_time

from core.views.home import ROW_SIZE
from tests.helpers import titles, type_counter_urls

ROWS = ["in_progress", "recently_rated", "planned", "empty_review"]


def _rows(response):
    """Return the title and the media titles of each row of the home page holding media, in their order."""
    rows = [response.context[name] for name in ROWS]
    return [(str(row["title"]), [media.title for media in row["media"]]) for row in rows if row["media"]]


@freeze_time("2026-10-01", auto_tick_seconds=60)
def test_rows_put_forward_media_in_progress_rated_planned_and_without_review(logged_in_client, media_factory):
    """The rows come in order, the last one holding the completed and abandoned media without a review."""
    media_factory(title="Reading", status="IN_PROGRESS")
    media_factory(title="Rated", status="COMPLETED", score=8, review="Great.")
    media_factory(title="Wishlist", status="PLANNED")
    media_factory(title="Finished", status="COMPLETED")
    media_factory(title="Dropped", status="DNF")
    media_factory(title="Paused", status="PAUSED")

    response = logged_in_client.get(reverse("home"))

    assert _rows(response) == [
        ("In progress", ["Reading"]),
        ("Recently rated", ["Rated"]),
        ("Planned", ["Wishlist"]),
        ("Empty review", ["Dropped", "Finished"]),
    ]


@freeze_time("2026-10-01", auto_tick_seconds=60)
@pytest.mark.parametrize(("status", "title"), [("IN_PROGRESS", "In progress"), ("PLANNED", "Planned")])
def test_status_rows_show_their_last_updated_media_first(logged_in_client, media_factory, status, title):
    """The in progress and planned rows show their last updated media first, as many as a row holds."""
    media = [media_factory(title=f"Media {index}", status=status) for index in range(ROW_SIZE + 1)]
    media[0].save()

    rows = dict(_rows(logged_in_client.get(reverse("home"))))

    assert rows[title] == ["Media 0", *[f"Media {index}" for index in range(ROW_SIZE, 1, -1)]]


@pytest.mark.parametrize(("title", "fields"), [("Recently rated", {"score": 7}), ("Empty review", {"status": "DNF"})])
def test_rows_of_finished_media_show_the_latest_reviewed_first(logged_in_client, media_factory, title, fields):
    """The recently rated and empty review rows show the latest reviewed media first, and the undated ones last."""
    media_factory(title="Old", review_date="2020", **fields)
    media_factory(title="New", review_date="2024-05", **fields)
    media_factory(title="Undated", **fields)

    rows = dict(_rows(logged_in_client.get(reverse("home"))))

    assert rows[title] == ["New", "Old", "Undated"]


def test_rows_without_media_are_hidden(logged_in_client, media_factory):
    """Only the rows holding media are shown, without the invitation of an empty library."""
    media_factory(title="Reading", status="IN_PROGRESS")

    content = logged_in_client.get(reverse("home")).content.decode()

    assert re.findall(r'<h2 class="card-title">([^<]*)</h2>', content) == ["In progress"]
    assert "Add your first media" not in content


def test_rows_link_to_their_list_and_their_media(logged_in_client, media_factory):
    """A status row links to the list of its media, the rated one to the whole list, and each card to its media."""
    for status in ["IN_PROGRESS", "PLANNED", "COMPLETED", "DNF", "PAUSED"]:
        media_factory(title=status, status=status)
    media_factory(title="Rated", status="COMPLETED", score=8, review="Great.")

    response = logged_in_client.get(reverse("home"))

    content = response.content.decode()
    rows = {str(response.context[name]["title"]): response.context[name] for name in ROWS}
    for title in ["In progress", "Planned", "Empty review"]:
        listed = titles(logged_in_client.get(rows[title]["url"]))
        assert set(listed) == {media.title for media in rows[title]["media"]}
    assert rows["Recently rated"]["url"] == reverse("media_list")
    for row in rows.values():
        assert f'href="{escape(row["url"])}"' in content
        for media in row["media"]:
            assert f'href="{reverse("media_detail", args=[media.pk])}"' in content


def test_rows_of_media_to_follow_up_show_smaller_cards(logged_in_client, media_factory):
    """Rows other than the recently rated one show smaller cards, without review nor date, but with their edit link."""
    reading = media_factory(title="Reading", status="IN_PROGRESS", review="Halfway through and hooked.")
    finished = media_factory(title="Finished", status="COMPLETED", review_date="2024-05-12")
    rated = media_factory(
        title="Rated", status="COMPLETED", score=8, review="Great until the end.", review_date="2025-05-04"
    )

    content = logged_in_client.get(reverse("home")).content.decode()

    assert "Halfway through and hooked." not in content
    assert "May 12, 2024" not in content
    assert "Great until the end." in content
    assert "May 4, 2025" in content
    for media in [reading, finished, rated]:
        assert f'href="{reverse("media_edit", args=[media.pk])}"' in content


@freeze_time("2026-10-21")
def test_home_sums_up_the_media_rated_this_year(logged_in_client, media_factory):
    """The home page counts the media rated this year for each type rated, leading to the stats of that type."""
    media_factory(media_type="BOOK", score=8, review_date="2026-03")
    media_factory(media_type="BOOK", score=6, review_date="2026")
    media_factory(media_type="FILM", score=9, review_date="2026-10-01")
    media_factory(media_type="FILM", score=7, review_date="2025-12-31")
    media_factory(media_type="FILM", review_date="2026-05")

    response = logged_in_client.get(reverse("home"))

    content = response.content.decode()
    assert [(row["media_type"], row["count"]) for row in response.context["type_counts"]] == [("BOOK", 2), ("FILM", 1)]
    assert "3 media rated in 2026" in content
    assert f'href="{reverse("stats")}?year=2026" class="btn' in content
    assert type_counter_urls(response) == [f"{reverse('stats')}?year=2026&type={value}" for value in ["BOOK", "FILM"]]


@freeze_time("2026-10-21")
def test_home_leaves_out_the_summary_of_a_year_without_rated_media(logged_in_client, media_factory):
    """Without any media rated this year, the home page has no summary of the year."""
    media_factory(score=7, review_date="2025")

    content = logged_in_client.get(reverse("home")).content.decode()

    assert "rated in 2026" not in content
    assert f"{reverse('stats')}?year=2026&amp;type=" not in content
