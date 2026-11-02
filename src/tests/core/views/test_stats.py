"""
Tests for core.views.stats: the statistics page.
"""

import pytest
from django.template.loader import render_to_string
from django.urls import reverse

from core.models import Agent, MediaType
from core.views.stats import STATS_COVERS_PER_PAGE
from tests.helpers import type_counter_urls


def test_stats_only_counts_rated_media(logged_in_client, media_factory):
    """Only rated media are counted, whatever their status."""
    media_factory(status="COMPLETED", review_date="2024", score=8)
    media_factory(status="DNF", review_date="2024", score=4)
    media_factory(status="COMPLETED", review_date="2023")

    response = logged_in_client.get(reverse("stats"))

    assert response.context["covers"].paginator.count == 2
    assert response.context["years"] == [2024]
    assert sum(row["count"] for row in response.context["type_counts"]) == 2


def test_stats_all_years_shows_yearly_chart(logged_in_client, media_factory):
    """Without a year, the yearly chart replaces the monthly one."""
    media_factory(review_date="2023-03-15", score=8)
    media_factory(review_date="2024-03-15", score=6)

    response = logged_in_client.get(reverse("stats"))

    assert [row["label"] for row in response.context["per_year"]] == [2023, 2024]
    assert response.context["per_month"] is None


def test_stats_yearly_bars_split_media_types_without_type_filter(logged_in_client, media_factory):
    """Without a type filter, the yearly bars split into media types, under a legend of the types with rated media."""
    media_factory(media_type="BOOK", review_date="2024", score=7)

    all_types = logged_in_client.get(reverse("stats")).content.decode()
    books = logged_in_client.get(reverse("stats"), {"type": "BOOK"}).content.decode()

    assert 'title="Books: 1"' in all_types
    assert "--color-type-book" in all_types
    assert "--color-type-film" not in all_types
    assert "--color-type-" not in books


def test_stats_year_shows_monthly_chart(logged_in_client, media_factory):
    """Selecting a year restricts the page to that year and shows the monthly chart instead of the yearly one."""
    media_factory(review_date="2023-06", score=2)
    media_factory(review_date="2024-03-15", score=8)

    response = logged_in_client.get(reverse("stats"), {"year": "2024"})

    assert response.context["year"] == 2024
    assert response.context["covers"].paginator.count == 1
    assert response.context["per_year"] is None
    assert response.context["per_month"][2]["count"] == 1


def test_stats_year_compares_with_year_before(logged_in_client, media_factory):
    """Type counters compare with the counts and pages of the year before, and the covers with its total of the type."""
    media_factory(media_type="BOOK", review_date="2023-05", page_count=300, score=7)
    media_factory(media_type="FILM", review_date="2023", score=7)
    media_factory(media_type="BOOK", review_date="2024", score=7)

    response = logged_in_client.get(reverse("stats"), {"year": 2024, "type": "BOOK"})

    rows = {row["media_type"]: row for row in response.context["type_counts"]}
    assert (rows["BOOK"]["previous"], rows["BOOK"]["previous_pages"], rows["FILM"]["previous"]) == (1, 300, 1)
    assert response.context["previous_count"] == 1


def test_stats_year_compares_with_calendar_year_before_only(logged_in_client, media_factory):
    """The year before is the calendar one, even without rated media; every year is compared with nothing."""
    media_factory(review_date="2022", score=7)
    media_factory(review_date="2024", score=7)

    year = logged_in_client.get(reverse("stats"), {"year": 2024})
    every_year = logged_in_client.get(reverse("stats"))

    assert year.context["previous_count"] == 0
    assert every_year.context["previous_count"] is None
    assert all("previous" not in row for row in every_year.context["type_counts"])


@pytest.mark.parametrize(
    ("count", "color", "difference"),
    [(3, "text-green-500", "+1"), (2, "text-base-content/60", "±0"), (1, "text-red-500", "-1")],
)
def test_stats_comparison_shows_signed_difference(count, color, difference):
    """A comparison shows its signed difference, tinted by its trend, and the previous count on hover."""
    context = {"count": count, "previous": 2, "year": 2023, "named": True}

    html = render_to_string("partials/stats/comparison.html", context)

    assert color in html
    assert f"{difference} compared with 2023" in html
    assert 'title="2 in 2023"' in html


def test_stats_comparison_without_year_hides_no_change():
    """Without the year, an unchanged count only shows its icon, while a fall to zero shows its difference."""
    unchanged = render_to_string("partials/stats/comparison.html", {"count": 2, "previous": 2, "year": 2023})
    fall = render_to_string("partials/stats/comparison.html", {"count": 0, "previous": 2, "year": 2023})

    assert "±0" not in unchanged
    assert "-2" in fall


def test_stats_comparison_localizes_thousands():
    """A comparison groups the thousands of its difference and of the previous count."""
    html = render_to_string("partials/stats/comparison.html", {"count": 2500, "previous": 1000, "year": 2023})

    assert "+1,500" in html
    assert 'title="1,000 in 2023"' in html


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
    assert response.context["covers"].paginator.count == 1
    assert response.context["score_distribution"][2]["count"] == 1
    assert response.context["score_distribution"][8]["count"] == 0
    counts = {row["media_type"]: row["count"] for row in response.context["type_counts"]}
    assert (counts["BOOK"], counts["FILM"]) == (1, 1)


@pytest.mark.parametrize(
    ("params", "film_query", "book_query"),
    [
        ({}, "type=FILM", "type=BOOK"),
        ({"year": "2024"}, "year=2024&type=FILM", "year=2024&type=BOOK"),
        ({"year": "2024", "type": "FILM"}, "year=2024", "year=2024&type=BOOK"),
    ],
)
def test_stats_type_counters_select_or_clear_their_type(logged_in_client, params, film_query, book_query):
    """A type counter narrows the stats down to its type, keeping the year, and the selected one clears the type."""
    urls = dict(zip(MediaType.values, type_counter_urls(logged_in_client.get(reverse("stats"), params)), strict=True))

    assert (urls["FILM"], urls["BOOK"]) == (f"{reverse('stats')}?{film_query}", f"{reverse('stats')}?{book_query}")


def test_stats_type_counters_show_their_pages(logged_in_client, media_factory):
    """The counter of a type with known page counts shows the pages of its rated media below their number."""
    media_factory(media_type="BOOK", page_count=1320, score=8)

    content = logged_in_client.get(reverse("stats")).content.decode()

    assert "1,320 pages" in content


@pytest.mark.parametrize("year", ["abc", "0", "9999", pytest.param("1" * 5000, id="oversized")])
def test_stats_invalid_filters_are_ignored(logged_in_client, media_factory, year):
    """Invalid type and year parameters, years out of the review date range included, fall back to everything."""
    media_factory(score=5)

    response = logged_in_client.get(reverse("stats"), {"year": year, "type": "NOPE"})

    assert response.context["year"] is None
    assert response.context["media_type"] is None
    assert response.context["covers"].paginator.count == 1


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


def _list_count(client, url):
    """Number of media listed at `url`."""
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
    assert response.context["covers"].paginator.count == bar["count"] == 2


def test_stats_month_bars_link_to_filtered_list(logged_in_client, media_factory):
    """Each monthly bar links to the media list filtered on that month."""
    media_factory(review_date="2024-02", score=7)
    media_factory(review_date="2024-02-29", score=7)
    media_factory(review_date="2024-03-01", score=7)

    response = logged_in_client.get(reverse("stats"), {"year": "2024"})

    february = response.context["per_month"][1]
    assert "review_from=2024-02-01" in february["url"]
    assert "review_to=2024-02-29" in february["url"]
    assert _list_count(logged_in_client, february["url"]) == february["count"] == 2


def test_stats_score_bars_link_to_filtered_list(logged_in_client, media_factory):
    """Each score bar links to the media list filtered on that score, keeping the selected year and type."""
    media_factory(media_type="GAME", review_date="2026-03", score=4)
    media_factory(media_type="GAME", review_date="2026", score=4)
    media_factory(media_type="GAME", review_date="2025-12-31", score=4)
    media_factory(media_type="FILM", review_date="2026-03", score=4)

    response = logged_in_client.get(reverse("stats"), {"year": "2026", "type": "GAME"})

    bar = response.context["score_distribution"][3]
    assert bar["label"] == 4
    assert _list_count(logged_in_client, bar["url"]) == bar["count"] == 2


@pytest.mark.parametrize(
    ("index", "inside", "outside"),
    [pytest.param(0, (-200, 1899), (1900,), id="before-1900"), pytest.param(8, (1970, 1979), (1969, 1980), id="1970s")],
)
def test_stats_decade_bars_link_to_filtered_list(logged_in_client, media_factory, index, inside, outside):
    """Each decade bar links to the media list filtered on its decade, keeping the selected year and type."""
    for pub_year in (*inside, *outside):
        media_factory(media_type="FILM", pub_year=pub_year, review_date="2024-05", score=7)
    media_factory(media_type="FILM", pub_year=inside[0], review_date="2023", score=7)
    media_factory(media_type="BOOK", pub_year=inside[0], review_date="2024", score=7)

    bar = logged_in_client.get(reverse("stats"), {"year": "2024", "type": "FILM"}).context["per_decade"][index]

    assert _list_count(logged_in_client, bar["url"]) == bar["count"] == 2


def test_stats_ranked_contributors_link_to_filtered_list(logged_in_client, media_factory):
    """Each ranked contributor links to the media list filtered on it, keeping the selected year and type."""
    agent = Agent.objects.create(name="Agent")
    for review_date in ("2024", "2024-05", "2024-12-31"):
        media_factory(media_type="FILM", review_date=review_date, score=7, contributors=[agent])
    media_factory(media_type="FILM", review_date="2023", score=7, contributors=[agent])
    media_factory(media_type="BOOK", review_date="2024", score=7, contributors=[agent])

    ranking = logged_in_client.get(reverse("stats"), {"year": "2024", "type": "FILM"}).context["contributors"]

    for row in (ranking["most_frequent"][0], ranking["best_rated"][0]):
        assert _list_count(logged_in_client, row["url"]) == row["count"] == 3
